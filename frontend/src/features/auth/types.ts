export interface User {
  id: string;
  username: string;
  email: string;
  created_at: string;
}

export interface AuthTokens {
  access_token: string;
  refresh_token?: string | null;
  token_type: string;
}

export interface AuthUserResponse {
  user: User;
}

export interface SignupInput {
  username: string;
  email: string;
  password: string;
}

export interface LoginInput {
  email: string;
  password: string;
}
