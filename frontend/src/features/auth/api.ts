import { api } from "../../shared/api";
import type {
  AuthTokens,
  AuthUserResponse,
  LoginInput,
  SignupInput,
} from "./types";

const REFRESH_TOKEN_STORAGE_KEY = "vault_refresh_token";

export function getStoredRefreshToken(): string | null {
  try {
    return localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredRefreshToken(token: string | null): void {
  try {
    if (token) {
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, token);
    } else {
      localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY);
    }
  } catch {
    // Ignore storage errors in restricted contexts
  }
}

export function signup(input: SignupInput): Promise<AuthUserResponse> {
  return api.post<AuthUserResponse>("/auth/signup", input);
}

export async function login(input: LoginInput): Promise<AuthTokens> {
  const tokens = await api.post<AuthTokens>("/auth/login", input);
  if (tokens.refresh_token) {
    setStoredRefreshToken(tokens.refresh_token);
  }
  return tokens;
}

let activeRefreshPromise: Promise<AuthTokens> | null = null;

export async function refreshSession(): Promise<AuthTokens> {
  if (activeRefreshPromise) {
    return activeRefreshPromise;
  }

  const storedToken = getStoredRefreshToken();
  activeRefreshPromise = api
    .post<AuthTokens>(
      "/auth/refresh",
      storedToken ? { refresh_token: storedToken } : undefined,
    )
    .then((tokens) => {
      if (tokens.refresh_token) {
        setStoredRefreshToken(tokens.refresh_token);
      }
      return tokens;
    })
    .catch((error) => {
      setStoredRefreshToken(null);
      throw error;
    })
    .finally(() => {
      activeRefreshPromise = null;
    });

  return activeRefreshPromise;
}

export async function logout(): Promise<null> {
  const storedToken = getStoredRefreshToken();
  try {
    return await api.post<null>(
      "/auth/logout",
      storedToken ? { refresh_token: storedToken } : undefined,
    );
  } finally {
    setStoredRefreshToken(null);
  }
}

export function getCurrentUser(): Promise<AuthUserResponse> {
  return api.get<AuthUserResponse>("/auth/me");
}
