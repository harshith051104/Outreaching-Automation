"use client";

import { useEffect, useState } from "react";

export interface User {
  id: string;
  name: string;
  email: string;
  role?: string;
}

export function useAuthStore() {
  const [user, setUser] = useState<User | null>(null);

  useEffect(() => {
    if (typeof window !== "undefined") {
      const userStr = localStorage.getItem("user");
      if (userStr) {
        try {
          setUser(JSON.parse(userStr));
        } catch (e) {
          setUser({ id: "demo-user", name: "Guest User", email: "user@example.com" });
        }
      } else {
        setUser({ id: "demo-user", name: "Guest User", email: "user@example.com" });
      }
    }
  }, []);

  return { user };
}
