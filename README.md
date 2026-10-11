# CloudVault — Cloud File Storage Application

CloudVault is a web-based cloud file storage application that allows users to securely register, log in, upload files, download their stored files, and delete files they no longer need.

## Features

- User registration and login
- Secure, user-specific file access
- File upload and download
- File deletion
- Cloud file storage using Supabase Storage
- File metadata stored in Supabase
- Responsive web interface
- Flask-powered backend

## Technology Stack

- **Backend:** Python, Flask
- **Frontend:** HTML, CSS
- **Authentication:** Supabase Auth
- **Database:** Supabase PostgreSQL
- **File Storage:** Supabase Storage
- **Deployment:** Render
- **Version Control:** Git and GitHub

## Live Demo

Add your deployed Render URL here.

## Source Code

https://github.com/mishkaat18/cloudfilestorage

## Local Setup

1. Clone the repository:

   ```bash
   git clone https://github.com/mishkaat18/cloudfilestorage.git
   cd cloudfilestorage
   ```

2. Create and activate a Python virtual environment:

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

3. Install the dependencies:

   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the project root with the following variables:

   ```env
   SUPABASE_URL = https://tbpikowqzqnvsefziaod.supabase.co
   SUPABASE_KEY = sb_publishable_0nOCtsoPwzJO4K4K1-JhzQ_2_79dV-V
   FLASK_SECRET_KEY = 1c69bf2f521cf0e0af24ceafe0b3cc08f3f808b172baab0f48683492f2959f60
   ```

5. Configure the Supabase project, database table, private storage bucket, and access policies according to your application configuration.

6. Run the application:

   ```bash
   python app.py
   ```

7. Open `http://127.0.0.1:5000` in your browser.

## Security Notes

- Keep `.env` and all credentials out of version control.
- Use a private storage bucket and user-specific access policies.
- Never expose Supabase secret or service-role keys in frontend code or public repositories.

## Project Status

Deployed on Render. Features should be tested before production use.

## Author

Developed as a cloud file storage application project.
