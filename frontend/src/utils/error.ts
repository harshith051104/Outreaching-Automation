/**
 * Safely extract a human-readable error message from an Axios error response.
 *
 * FastAPI may return `detail` as either:
 * - A string (e.g. "Email already registered")
 * - An array of validation error objects [{type, loc, msg, input}, ...]
 *
 * This helper normalises both shapes into a displayable string.
 */
export function extractErrorMessage(err: any, fallback = "Something went wrong"): string {
  const detail = err?.response?.data?.detail;

  if (!detail) {
    return err?.message || fallback;
  }

  // Simple string detail
  if (typeof detail === "string") {
    return detail;
  }

  // Array of Pydantic validation errors
  if (Array.isArray(detail)) {
    return detail
      .map((item: any) => {
        if (typeof item === "string") return item;
        // item.loc is like ["body", "email"] — take the last part as the field name
        const field = Array.isArray(item.loc)
          ? item.loc[item.loc.length - 1]
          : "";
        const msg = item.msg || "Invalid value";
        return field ? `${field}: ${msg}` : msg;
      })
      .join(". ");
  }

  // Object with a message property
  if (typeof detail === "object" && detail.msg) {
    return detail.msg;
  }

  return fallback;
}
