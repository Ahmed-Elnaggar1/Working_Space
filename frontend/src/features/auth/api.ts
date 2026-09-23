import { api } from "../../shared/api";
import type {
  AuthTokens,
  AuthUserResponse,
  LoginInput,
  SignupInput,
} from "./types";

export function signup(input: SignupInput): Promise<AuthUserResponse> {
  return api.post<AuthUserResponse>("/auth/signup", input);
}

export function login(input: LoginInput): Promise<AuthTokens> {
  return api.post<AuthTokens>("/auth/login", input);
}

export function refreshSession(): Promise<AuthTokens> {
  return api.post<AuthTokens>("/auth/refresh");
}

export function logout(): Promise<null> {
  return api.post<null>("/auth/logout");
}

export function getCurrentUser(): Promise<AuthUserResponse> {
  return api.get<AuthUserResponse>("/auth/me");
}
