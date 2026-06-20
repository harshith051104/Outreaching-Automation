import argparse
import asyncio
import json
import sys
import logging
from datetime import datetime, timezone

# Configure basic logging to stderr so it doesn't pollute stdout (where JSON is printed)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger("linkedin_runner")

async def main():
    parser = argparse.ArgumentParser(description="LinkedIn Playwright Subprocess Runner")
    parser.add_argument("--action", required=True, help="Action to execute")
    parser.add_argument("--user-id", required=True, help="User ID")
    parser.add_argument("--linkedin-url", help="Target LinkedIn URL")
    parser.add_argument("--message", help="Message or note content")
    args = parser.parse_args()

    if sys.platform == "win32":
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception as e:
            logger.warning(f"Could not set ProactorEventLoopPolicy: {e}")

    logger.info(f"Starting linkedin_runner for action '{args.action}', user '{args.user_id}'")

    from app.config.mongodb_config import get_database, mongodb_client

    await mongodb_client.connect()
    logger.info("MongoDB connected")

    result = {"success": False, "error": "Unknown action"}

    async def _safe_decrypt(db, session_doc) -> str | None:
        """
        Decrypt cookies safely. If decryption fails (stale/rotated key),
        marks the session as expired in MongoDB and returns None so the caller
        can exit gracefully rather than crash.
        """
        from app.services.linkedin_outreach_service import _decrypt_cookies
        try:
            return _decrypt_cookies(session_doc["cookies_encrypted"])
        except (ValueError, Exception) as exc:
            logger.error(
                "Cookie decryption failed for user %s — marking session as expired. Reason: %s",
                args.user_id, exc,
            )
            await db.linkedin_sessions.update_one(
                {"user_id": args.user_id},
                {"$set": {
                    "status": "expired",
                    "updated_at": datetime.now(timezone.utc),
                    "error": "Encryption key changed. Please re-connect your LinkedIn account.",
                }},
            )
            return None

    try:
        db = await get_database()

        session = await db.linkedin_sessions.find_one({"user_id": args.user_id})

        if args.action == "start_session":
            from app.services.linkedin_outreach_service import _start_session_pw, _encrypt_cookies
            try:
                res = await asyncio.wait_for(_start_session_pw(), timeout=120)
            except asyncio.TimeoutError:
                res = {"status": "login_timeout", "message": "Login timed out after 120s. Please try again."}
            if res.get("status") == "success" and res.get("cookies"):
                cookies = res["cookies"]
                cookies_json = json.dumps(cookies)
                encrypted_cookies = _encrypt_cookies(cookies_json)
                now = datetime.now(timezone.utc)
                update_fields = {
                    "user_id": args.user_id,
                    "cookies_encrypted": encrypted_cookies,
                    "status": "connected",
                    "last_validated_at": now,
                    "created_at": now,
                    "updated_at": now,
                }
                if res.get("account_name"):
                    update_fields["account_name"] = res["account_name"]
                if res.get("avatar_url"):
                    update_fields["avatar_url"] = res["avatar_url"]

                await db.linkedin_sessions.update_one(
                    {"user_id": args.user_id},
                    {"$set": update_fields},
                    upsert=True
                )
                result = {"status": "connected", "message": "LinkedIn session established successfully."}
            elif res.get("status") == "login_timeout":
                result = {"status": "login_timeout", "message": "Login timed out. Please try again."}
            else:
                result = {"status": "error", "message": res.get("message", "Failed to login")}

        elif args.action == "validate_session":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                from app.services.linkedin_outreach_service import _decrypt_cookies
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"valid": False, "status": "expired", "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _validate_session_pw
                    try:
                        val_res = await asyncio.wait_for(_validate_session_pw(cookies), timeout=30)
                    except asyncio.TimeoutError:
                        logger.warning("validate_session timed out after 30s")
                        val_res = {"valid": False, "error": "Session validation timed out"}
                    is_valid = val_res.get("valid", False) if isinstance(val_res, dict) else val_res
                    if is_valid:
                        update_fields = {
                            "last_validated_at": datetime.now(timezone.utc),
                            "status": "connected"
                        }
                        if isinstance(val_res, dict):
                            if val_res.get("account_name"):
                                update_fields["account_name"] = val_res["account_name"]
                            if val_res.get("avatar_url"):
                                update_fields["avatar_url"] = val_res["avatar_url"]
                                
                        await db.linkedin_sessions.update_one(
                            {"user_id": args.user_id},
                            {"$set": update_fields}
                        )
                        result = {"valid": True, "status": "connected"}
                    else:
                        await db.linkedin_sessions.update_one(
                            {"user_id": args.user_id},
                            {"$set": {"status": "expired"}}
                        )
                        result = {"valid": False, "status": "expired"}

        elif args.action == "scrape_profile":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _scrape_profile_pw
                    try:
                        res = await asyncio.wait_for(
                            _scrape_profile_pw(args.linkedin_url, cookies),
                            timeout=60
                        )
                    except asyncio.TimeoutError:
                        logger.warning("scrape_profile timed out after 60s for %s", args.linkedin_url)
                        res = {"success": False, "error": "Profile scrape timed out after 60s"}
                    if isinstance(res, dict) and "error" in res and "Session expired" in res.get("error", ""):
                        await db.linkedin_sessions.update_one(
                            {"user_id": args.user_id},
                            {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                        )
                    if isinstance(res, dict) and res.get("error_screenshot_path"):
                        scr_path = res.pop("error_screenshot_path")
                        try:
                            import os
                            from app.utils.id_generator import generate_id
                            file_id = generate_id()
                            filename = os.path.basename(scr_path)
                            file_doc = {
                                "id": file_id,
                                "user_id": args.user_id,
                                "original_filename": filename,
                                "stored_filename": filename,
                                "file_path": scr_path,
                                "content_type": "image/png",
                                "file_size": os.path.getsize(scr_path) if os.path.exists(scr_path) else 0,
                                "download_url": f"/api/files/{file_id}/download",
                                "created_at": datetime.now(timezone.utc),
                            }
                            await db.uploaded_files.insert_one(file_doc)
                            res["error_screenshot"] = f"/api/files/{file_id}/download"
                        except Exception as db_exc:
                            logger.error("Failed to save error screenshot to DB: %s", db_exc)
                    result = res

        elif args.action == "send_connection_request":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings -> Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _send_connection_request_pw
                    try:
                        res = await asyncio.wait_for(
                            _send_connection_request_pw(args.linkedin_url, args.message, cookies),
                            timeout=300
                        )
                    except asyncio.TimeoutError:
                        logger.warning("send_connection_request timed out after 300s for %s", args.linkedin_url)
                        res = {"success": False, "error": "Connection request timed out after 300s. LinkedIn may be slow or blocked."}
                    if not res.get("success") and "Session expired" in res.get("error", ""):
                        await db.linkedin_sessions.update_one(
                            {"user_id": args.user_id},
                            {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                        )
                    if isinstance(res, dict) and res.get("error_screenshot_path"):
                        scr_path = res.pop("error_screenshot_path")
                        try:
                            import os
                            from app.utils.id_generator import generate_id
                            file_id = generate_id()
                            filename = os.path.basename(scr_path)
                            file_doc = {
                                "id": file_id,
                                "user_id": args.user_id,
                                "original_filename": filename,
                                "stored_filename": filename,
                                "file_path": scr_path,
                                "content_type": "image/png",
                                "file_size": os.path.getsize(scr_path) if os.path.exists(scr_path) else 0,
                                "download_url": f"/api/files/{file_id}/download",
                                "created_at": datetime.now(timezone.utc),
                            }
                            await db.uploaded_files.insert_one(file_doc)
                            res["error_screenshot"] = f"/api/files/{file_id}/download"
                        except Exception as db_exc:
                            logger.error("Failed to save screenshot: %s", db_exc)
                    result = res

        elif args.action == "follow_profile":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _follow_profile_pw
                    try:
                        res = await asyncio.wait_for(
                            _follow_profile_pw(args.linkedin_url, cookies),
                            timeout=60
                        )
                    except asyncio.TimeoutError:
                        logger.warning("follow_profile timed out after 60s for %s", args.linkedin_url)
                        res = {"success": False, "error": "Follow profile timed out after 60s"}
                if not res.get("success") and "Session expired" in res.get("error", ""):
                    await db.linkedin_sessions.update_one(
                        {"user_id": args.user_id},
                        {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                    )
                if isinstance(res, dict) and res.get("error_screenshot_path"):
                    scr_path = res.pop("error_screenshot_path")
                    try:
                        import os
                        from app.utils.id_generator import generate_id
                        file_id = generate_id()
                        filename = os.path.basename(scr_path)
                        file_doc = {
                            "id": file_id,
                            "user_id": args.user_id,
                            "original_filename": filename,
                            "stored_filename": filename,
                            "file_path": scr_path,
                            "content_type": "image/png",
                            "file_size": os.path.getsize(scr_path) if os.path.exists(scr_path) else 0,
                            "download_url": f"/api/files/{file_id}/download",
                            "created_at": datetime.now(timezone.utc),
                        }
                        await db.uploaded_files.insert_one(file_doc)
                        res["error_screenshot"] = f"/api/files/{file_id}/download"
                    except Exception as db_exc:
                        logger.error("Failed to save screenshot: %s", db_exc)
                result = res

        elif args.action == "send_message":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _send_message_pw
                try:
                    res = await asyncio.wait_for(
                        _send_message_pw(args.linkedin_url, args.message, cookies),
                        timeout=60
                    )
                except asyncio.TimeoutError:
                    logger.warning("send_message timed out after 60s for %s", args.linkedin_url)
                    res = {"success": False, "error": "Send message timed out after 60s"}
                if not res.get("success") and "Session expired" in res.get("error", ""):
                    await db.linkedin_sessions.update_one(
                        {"user_id": args.user_id},
                        {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                    )
                if isinstance(res, dict) and res.get("error_screenshot_path"):
                    scr_path = res.pop("error_screenshot_path")
                    try:
                        import os
                        from app.utils.id_generator import generate_id
                        file_id = generate_id()
                        filename = os.path.basename(scr_path)
                        file_doc = {
                            "id": file_id,
                            "user_id": args.user_id,
                            "original_filename": filename,
                            "stored_filename": filename,
                            "file_path": scr_path,
                            "content_type": "image/png",
                            "file_size": os.path.getsize(scr_path) if os.path.exists(scr_path) else 0,
                            "download_url": f"/api/files/{file_id}/download",
                            "created_at": datetime.now(timezone.utc),
                        }
                        await db.uploaded_files.insert_one(file_doc)
                        res["error_screenshot"] = f"/api/files/{file_id}/download"
                    except Exception as db_exc:
                        logger.error("Failed to save screenshot: %s", db_exc)
                result = res

        elif args.action == "send_message_by_name":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _send_message_by_name_pw
                    # Unpack person_name and message from the packed format "name|||message"
                packed = args.message or ""
                if "|||" in packed:
                    person_name, msg_text = packed.split("|||", 1)
                else:
                    person_name = packed
                    msg_text = ""
                try:
                    res = await asyncio.wait_for(
                        _send_message_by_name_pw(person_name, msg_text, cookies),
                        timeout=90
                    )
                except asyncio.TimeoutError:
                    logger.warning("send_message_by_name timed out after 90s for '%s'", person_name)
                    res = {"success": False, "error": "Send message by name timed out after 90s"}
                if not res.get("success") and "Session expired" in res.get("error", ""):
                    await db.linkedin_sessions.update_one(
                        {"user_id": args.user_id},
                        {"$set": {"status": "expired", "updated_at": datetime.now(timezone.utc)}}
                    )
                if isinstance(res, dict) and res.get("error_screenshot_path"):
                    scr_path = res.pop("error_screenshot_path")
                    try:
                        import os
                        from app.utils.id_generator import generate_id
                        file_id = generate_id()
                        filename = os.path.basename(scr_path)
                        file_doc = {
                            "id": file_id,
                            "user_id": args.user_id,
                            "original_filename": filename,
                            "stored_filename": filename,
                            "file_path": scr_path,
                            "content_type": "image/png",
                            "file_size": os.path.getsize(scr_path) if os.path.exists(scr_path) else 0,
                            "download_url": f"/api/files/{file_id}/download",
                            "created_at": datetime.now(timezone.utc),
                        }
                        await db.uploaded_files.insert_one(file_doc)
                        res["error_screenshot"] = f"/api/files/{file_id}/download"
                    except Exception as db_exc:
                        logger.error("Failed to save screenshot: %s", db_exc)
                result = res

        elif args.action == "get_pending_invitations":
            if not session or not session.get("cookies_encrypted"):
                result = {"success": False, "error": "No active LinkedIn session."}
            else:
                cookies_json = await _safe_decrypt(db, session)
                if cookies_json is None:
                    result = {"success": False, "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."}
                else:
                    cookies = json.loads(cookies_json)
                    from app.services.linkedin_outreach_service import _get_pending_invitations_pw
                    try:
                        res = await asyncio.wait_for(
                            _get_pending_invitations_pw(cookies),
                            timeout=60
                        )
                        if isinstance(res, dict) and "error" in res and "Session expired" in res.get("error", ""):
                            logger.warning("Session expired detected in get_pending_invitations. Marking session as expired.")
                            await db.linkedin_sessions.update_one(
                                {"user_id": args.user_id},
                                {"$set": {
                                    "status": "expired",
                                    "updated_at": datetime.now(timezone.utc),
                                    "error": "LinkedIn session expired. Please re-connect via Settings → Integrations."
                                }}
                            )
                        result = res
                    except asyncio.TimeoutError:
                        logger.warning("get_pending_invitations timed out after 60s")
                        result = {"success": False, "error": "Getting pending invitations timed out after 60s"}

    except Exception as e:
        logger.exception(f"Runner failed to execute action {args.action}")
        err_msg = str(e) if str(e) else f"{type(e).__name__}"
        result = {"success": False, "error": err_msg}
    finally:
        await mongodb_client.disconnect()
        print(f"__RESULT__={json.dumps(result)}")

if __name__ == "__main__":
    asyncio.run(main())
