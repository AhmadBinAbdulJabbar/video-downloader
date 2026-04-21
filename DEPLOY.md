# Deploying to Render.com

## Step 1: Push to GitHub

```bash
cd /home/ahmad/Dev/projects/youtube_downloader

# Initialize git repo
git init
git add -A
git commit -m "Initial commit: Video downloader for YouTube and Facebook"
git branch -M main

# Add your GitHub repo as remote
git remote add origin https://github.com/YOUR_USERNAME/youtube-downloader.git
git push -u origin main
```

## Step 2: Create Render Service

1. Go to [render.com](https://render.com)
2. Sign up or log in with GitHub
3. Click **New +** → **Web Service**
4. Connect your GitHub repository
5. Fill in the service details:
   - **Name**: `video-downloader` (or any name)
   - **Environment**: `Python 3.11`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 8080`
   - **Plan**: Free tier (or paid for no sleep time)

## Step 3: Deploy

Click "Deploy" and Render will:
- Build your app (install dependencies)
- Start the service
- Give you a live URL like `https://video-downloader.onrender.com`

## Notes

- **Free Tier**: Spins down after 15 minutes of inactivity. First request takes ~30s to wake up. Upgrade to remove this.
- **yt-dlp**: Works on Render's Linux containers. First download may take time as it downloads metadata.
- **Temporary Files**: Downloads are stored in `/tmp` and auto-cleaned.
- **Timeout**: Render free tier has 30-second HTTP timeout. Large downloads might timeout—upgrade for reliability.

## Environment Variables (Optional)

If you need environment-specific settings, you can add them in Render's dashboard:
- Dashboard → Select your service → Settings → Environment Variables

Currently not needed, but available for future use.

## Troubleshooting

**Build fails?**
- Check Render logs: Your service → Logs
- Ensure `requirements.txt` has all dependencies

**Downloads timeout?**
- Free tier limits: Upgrade to Paid tier for longer timeouts
- Or use smaller files for testing

**yt-dlp errors?**
- Some videos may be region-restricted or unavailable
- Check browser console (F12) for error details
