import axios from "axios";

import { getToken, removeToken, setToken } from "@/utils/token";

/**
 * Axios instance configured for the backend API.
 *
 * In development, Vite proxies /auth and /api to the backend,
 * so we use an empty baseURL (relative paths).
 * In production, set VITE_API_BASE_URL to the backend origin.
 */
const BASE_URL = import.meta.env.DEV ? "" : import.meta.env.VITE_API_BASE_URL || "";

const api = axios.create({
  baseURL: BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor: attach JWT token
api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

let isRefreshing = false;
let refreshQueue: Array<(token: string) => void> = [];

function drainQueue(newToken: string) {
  refreshQueue.forEach((resolve) => resolve(newToken));
  refreshQueue = [];
}

function clearSession() {
  removeToken();
  if (window.location.pathname !== "/login") {
    window.location.href = "/login";
  }
}

// Response interceptor: on 401, attempt token refresh before giving up
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    if (
      !axios.isAxiosError(error) ||
      error.response?.status !== 401 ||
      originalRequest._retry ||
      originalRequest.url?.includes("/auth/refresh") ||
      originalRequest.url?.includes("/auth/login") ||
      originalRequest.url?.includes("/auth/logout")
    ) {
      return Promise.reject(error);
    }

    originalRequest._retry = true;

    if (isRefreshing) {
      return new Promise((resolve) => {
        refreshQueue.push((token: string) => {
          originalRequest.headers.Authorization = `Bearer ${token}`;
          resolve(api(originalRequest));
        });
      });
    }

    isRefreshing = true;

    try {
      // Refresh token is an HttpOnly cookie — browser sends it automatically.
      const response = await axios.post(`${BASE_URL}/auth/refresh`, null, {
        withCredentials: true,
      });
      const { access_token } = response.data;
      setToken(access_token);
      drainQueue(access_token);
      originalRequest.headers.Authorization = `Bearer ${access_token}`;
      return api(originalRequest);
    } catch {
      clearSession();
      return Promise.reject(error);
    } finally {
      isRefreshing = false;
    }
  },
);

export default api;
