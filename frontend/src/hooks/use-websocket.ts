"use client";

import { useEffect, useRef, useCallback, useState } from "react";

type WebSocketMessage = {
  type: string;
  data: Record<string, unknown>;
};

type UseWebSocketOptions = {
  userId: string;
  onMessage?: (message: WebSocketMessage) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  enabled?: boolean;
};

export function useWebSocket({
  userId,
  onMessage,
  onConnect,
  onDisconnect,
  enabled = true,
}: UseWebSocketOptions) {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttempts = useRef(0);
  const maxReconnectAttempts = 10;
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);

  const connect = useCallback(() => {
    if (!enabled || !userId) return;

    // Don't try to connect too many times
    if (reconnectAttempts.current >= maxReconnectAttempts) {
      console.log("Max WebSocket reconnect attempts reached");
      return;
    }

    // Clean up existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    let wsUrl = `ws://127.0.0.1:8000/api/reply-monitor/ws/${userId}`;
    const publicApiUrl = process.env.NEXT_PUBLIC_API_URL;
    
    if (typeof window !== "undefined") {
      const loc = window.location;
      // If we are accessed remotely via a public URL (e.g. ngrok), use the current host relative URL
      if (loc.hostname !== "localhost" && loc.hostname !== "127.0.0.1") {
        const protocol = loc.protocol === "https:" ? "wss:" : "ws:";
        wsUrl = `${protocol}//${loc.host}/api/reply-monitor/ws/${userId}`;
      } else if (publicApiUrl) {
        let baseUrl = publicApiUrl;
        if (baseUrl.endsWith("/")) {
          baseUrl = baseUrl.slice(0, -1);
        }
        if (!baseUrl.endsWith("/api") && !baseUrl.includes("/api/")) {
          baseUrl = `${baseUrl}/api`;
        }
        // Convert http:// -> ws:// and https:// -> wss://, replacing localhost with 127.0.0.1
        wsUrl = `${baseUrl.replace(/^http/, "ws").replace("localhost", "127.0.0.1")}/reply-monitor/ws/${userId}`;
      }
    }

    try {
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;

      ws.onopen = () => {
        setIsConnected(true);
        reconnectAttempts.current = 0;
        onConnect?.();
        console.log("WebSocket connected");
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (e) {
          // Ignore non-JSON messages (like pong responses)
        }
      };

      ws.onclose = (event) => {
        setIsConnected(false);
        onDisconnect?.();

        // Only reconnect if it wasn't a clean close
        if (event.code !== 1000) {
          const delay = Math.min(1000 * Math.pow(2, reconnectAttempts.current), 30000);
          reconnectAttempts.current += 1;
          console.log(`WebSocket disconnected, reconnecting in ${delay}ms...`);

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, delay);
        }
      };

      ws.onerror = () => {
        // Don't log error details - just close and let onhandle reconnect
        ws.close();
      };
    } catch (error) {
      console.error("Failed to create WebSocket:", error);
    }
  }, [userId, enabled, onMessage, onConnect, onDisconnect]);

  const disconnect = useCallback(() => {
    reconnectAttempts.current = maxReconnectAttempts; // Prevent reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }
    if (wsRef.current) {
      wsRef.current.close(1000); // Clean close
      wsRef.current = null;
    }
    setIsConnected(false);
  }, []);

  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);
    }
  }, []);

  useEffect(() => {
    connect();
    return () => disconnect();
  }, [connect, disconnect]);

  // Send periodic pings to keep connection alive
  useEffect(() => {
    if (!isConnected) return;

    const interval = setInterval(() => {
      sendMessage("ping");
    }, 30000);

    return () => clearInterval(interval);
  }, [isConnected, sendMessage]);

  return {
    isConnected,
    lastMessage,
    sendMessage,
    disconnect,
    reconnect: connect,
  };
}
