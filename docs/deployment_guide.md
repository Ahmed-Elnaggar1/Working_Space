# Deployment Guide: Supabase, Render, and Vercel

This guide walks you through deploying your full-stack application. Our deployment architecture is:
- **Database:** Supabase (PostgreSQL with pgvector)
- **Backend:** Render (Docker Web Service for FastAPI)
- **Frontend:** Vercel (Vite + React)

## Prerequisites
Before you start, ensure your project is pushed to a single GitHub repository. This will be used by both Render and Vercel for continuous deployment.

---

## Step 1: Set up Supabase (Database)

1. Go to [Supabase](https://supabase.com/) and create a new project.
2. Provide a project name, a secure database password, and select a region close to your target audience. Wait for the database to finish provisioning.
3. Once provisioned, go to **Project Settings -> Database** (or click the "Connect" button at the top).
4. Scroll to the **Connection string** section, select **URI**, and copy it (it should start with `postgresql://`).
5. Replace `[YOUR-PASSWORD]` in the connection string with the password you created in step 2.
6. **Save this connection string**, you will need it for the Render backend.

---

## Step 2: Deploy Backend to Render

1. Go to [Render](https://render.com/) and create an account or sign in.
2. Click **New +** and select **Web Service**.
3. Connect your GitHub account and select your project's repository.
4. **Configuration details:**
   - **Name:** Choose a name for your backend (e.g., `vault-backend`).
   - **Root Directory:** Type `backend`. (This is critical so Render finds the `Dockerfile`).
   - **Environment:** Select **Docker**.
   - **Branch:** `main` (or your default branch).
   - **Instance Type:** Free (if available) or the lowest paid tier.
5. **Environment Variables:** Scroll down to the Advanced / Environment Variables section and add the following based on your project's `app/core/config.py`:
   - `DATABASE_URL`: Paste the Supabase connection string from Step 1.
   - `ENV`: `production`
   - `JWT_ACCESS_SECRET`: Generate a secure random string for access tokens.
   - `JWT_REFRESH_SECRET`: Generate a secure random string for refresh tokens.
   - `LLM_PROVIDER`: Set to `gemini` (or `claude`).
   - `GEMINI_API_KEY`: Your Gemini API Key (if `LLM_PROVIDER=gemini`).
   - `ANTHROPIC_API_KEY`: Your Anthropic API Key (if `LLM_PROVIDER=claude`).
   - *(Optional but Recommended for Persistent File Storage on Render)*:
     - `S3_BUCKET_NAME`: Your AWS S3 (or R2/Cloudflare) bucket name.
     - `AWS_ACCESS_KEY_ID`: Your AWS access key.
     - `AWS_SECRET_ACCESS_KEY`: Your AWS secret key.
     - `AWS_ENDPOINT_URL`: Your S3 endpoint URL (if not using standard AWS).
6. Click **Create Web Service**. 
7. Wait for the deployment to finish. Render will build the Docker container and start it. The Dockerfile is already configured to automatically run `alembic upgrade head` before starting the web server, which will automatically set up your database tables on Supabase!
8. Once the deployment says "Live", **copy the Render URL** provided at the top (e.g., `https://vault-backend-xxxx.onrender.com`). You will need this for Vercel.

---

## Step 3: Deploy Frontend to Vercel

1. Go to [Vercel](https://vercel.com/) and sign in with your GitHub account.
2. Click **Add New... -> Project**.
3. Import the same GitHub repository you used for Render.
4. **Configuration details:**
   - **Project Name:** Choose a name for your frontend (e.g., `vault-frontend`).
   - **Framework Preset:** Vite (Vercel usually auto-detects this).
   - **Root Directory:** Click "Edit" and select `frontend`. 
   - **Build and Output Settings:** Leave default (`npm run build` and `dist` output).
5. **Environment Variables:**
   - Name: `VITE_API_BASE_URL`
   - Value: Paste the **Render backend URL** you copied in Step 2 (e.g., `https://vault-backend-xxxx.onrender.com`). *Make sure there is no trailing slash.*
6. Click **Deploy**.
7. Wait for Vercel to build and deploy your frontend. Once complete, you will get a live `.vercel.app` URL.

---

## Step 4: Verify Your Deployment

1. Visit the Vercel frontend URL in your browser.
2. Test core functionality (creating an account, querying data, etc.) to confirm everything is wired up correctly!

### Troubleshooting
- **Database Connections:** If the backend fails to connect to the database, double-check your Supabase `DATABASE_URL` in the Render environment variables. Ensure the password is correct and special characters are URL-encoded.
- **CORS Issues:** If your frontend receives a CORS error, you may need to update the backend CORS configuration to explicitly allow your Vercel URL instead of just `*` or `localhost`.
- **Database Migrations:** If endpoints return 500 errors regarding missing tables, ensure the Render build logs show `alembic upgrade head` running successfully.
