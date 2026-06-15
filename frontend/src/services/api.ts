import axios from "axios";

let ssrBaseUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api";
if (ssrBaseUrl.endsWith("/")) {
  ssrBaseUrl = ssrBaseUrl.slice(0, -1);
}
if (!ssrBaseUrl.endsWith("/api") && !ssrBaseUrl.includes("/api/")) {
  ssrBaseUrl = `${ssrBaseUrl}/api`;
}

const api = axios.create({
  baseURL: typeof window !== "undefined"
    ? "/api"  // relative path — works through same-origin proxy (ngrok) and in production
    : ssrBaseUrl,  // SSR fallback
  headers: {
    "Content-Type": "application/json",
  },
});

api.interceptors.request.use(
  (config) => {
    if (typeof window !== "undefined") {
      const token = localStorage.getItem("access_token");
      if (token) {
        config.headers.Authorization = `Bearer ${token}`;
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("user");
      window.location.href = "/login";
    }
    if (!error.response && error.code === "ERR_NETWORK") {
      error.message =
        "Unable to connect to the server. Please ensure the backend is running at " +
        (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000");
    }
    return Promise.reject(error);
  }
);

export default api;
