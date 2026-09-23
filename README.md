# Coders Site — Django LMS

<p align="center">
  A modern Learning Management System built with Django.
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.x-blue?logo=python" alt="Python">
  <img src="https://img.shields.io/badge/Django-5.2-green?logo=django" alt="Django">
  <img src="https://img.shields.io/badge/Bootstrap-5-purple?logo=bootstrap" alt="Bootstrap">
  <img src="https://img.shields.io/badge/PostgreSQL-Supported-blue?logo=postgresql" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/License-MIT-yellow" alt="License">
</p>

## 📖 About

**Coders Site** is a full-featured Learning Management System built with **Django** for managing online courses, instructors, students, learning content, reviews, and educational articles.

The platform provides separate experiences for **students and instructors**, with role-based access, course management, instructor dashboards, student dashboards, progress tracking, blogging, and community Q&A features.

## ✨ Features

### 🔐 Authentication & Users

* Custom Django user model
* Student, instructor, and admin roles
* User registration and login
* Logout and password reset
* Profile and avatar management
* Remember-me session support
* Role-based access control

### 🎓 Course Management

* Course categories
* Course sections and lessons
* MP4 lesson video uploads
* Course pricing and discounts
* Free and paid courses
* Skill levels
* Course tags
* Course certification flag
* Course views and publishing status
* Instructor-specific course management

### 📚 Learning & Progress

* Course enrollment model
* Lesson progress tracking
* Course progress tracking
* Completed lessons and completed courses
* Certificate tracking
* Student course dashboard
* Personal course list
* Learning progress calculation

### 👨‍🏫 Instructor Dashboard

* Instructor profile
* Instructor courses
* Course creation
* Section and lesson creation
* Student statistics
* Course sales statistics
* Monthly revenue analytics
* Course pagination
* Instructor education and skills

### ⭐ Reviews & Discussions

* Course ratings from 1 to 5
* Course comments
* Comment replies
* Comment likes
* One rating per user for each course
* Moderation support through published status

### 📝 Blog System

* Blog posts and categories
* Tags with `django-taggit`
* Rich text content with CKEditor
* Post search
* Author, category, and tag filtering
* Post comments and replies
* Post view counter
* Post likes
* Jalali date formatting

### 💬 Community & Support

* Frequently asked questions
* User questions and answers
* Question categories
* Question likes
* Contact form
* Instructor and mentor sections
* Course and website search

### 🔎 Search & Navigation

* Course search
* Blog search
* Instructor search
* Category filtering
* Tag filtering
* Skill-level filtering
* Free/paid filtering
* Sorting by newest, rating, and views
* Pagination

### 🛡️ Security & SEO

* Django CSRF protection
* Password validation
* Authentication controls
* reCAPTCHA v3 for authentication
* Cloudflare Turnstile for contact forms
* Clickjacking protection
* Content-type protection
* Security middleware
* Environment-based configuration
* `robots.txt`
* XML sitemap
* RSS feeds for courses and blog posts
* Open Graph and Twitter metadata

### 📱 Frontend

* Bootstrap 5
* Responsive layout
* RTL interface
* Persian localization
* Light and dark mode
* Responsive navigation
* Rich UI components and dashboards

## 🛠️ Tech Stack

| Technology      | Purpose                         |
| --------------- | ------------------------------- |
| Python          | Backend                         |
| Django 5.2      | Web framework                   |
| Bootstrap 5     | Frontend                        |
| SQLite          | Development database            |
| PostgreSQL      | Production database support     |
| CKEditor        | Rich text editing               |
| django-taggit   | Course and blog tags            |
| django-ckeditor | Rich content management         |
| WhiteNoise      | Static file serving             |
| Gunicorn        | WSGI server                     |
| django-csp      | Security middleware             |
| django-robots   | Robots configuration            |
| Django Sitemap  | SEO sitemap                     |
| Cloudinary      | Cloud media package integration |

## 📁 Project Structure

```text
Coders-Site-Django/
├── authentication/      # Authentication and custom user model
├── blog/                # Blog posts, comments and tags
├── course/              # Courses, lessons, enrollment and progress
├── dashboard/           # Student dashboard
├── instructor/          # Instructor profiles and dashboard
├── website/             # Homepage, FAQ, search and contact
├── coders/              # Django project configuration
├── templates/           # HTML templates
├── static/              # Static assets
├── media/               # Uploaded media files
├── manage.py
└── requirements.txt
```

## 🗄️ Main Data Models

The main learning domain is built around the following models:

```text
CustomUser
    │
    ├── Instructor
    │      ├── Education
    │      └── Skill
    │
    └── Student
           │
           ├── Enrollment
           ├── Purchase
           ├── LessonProgress
           ├── CourseProgress
           ├── Score
           └── Comments

Course
    ├── Category
    ├── Section
    │     └── Lesson
    ├── Score
    ├── Comment
    ├── FAQ
    └── Purchase
```

## 🔄 Learning Flow

```text
Register
   ↓
Login
   ↓
Browse Courses
   ↓
Filter / Search Courses
   ↓
View Course Details
   ↓
Enrollment / Purchase Record
   ↓
Access Course Content
   ↓
Track Lesson Progress
   ↓
Complete Course
   ↓
Certificate / Review
```

## ⚙️ Installation

### 1. Clone the repository

```bash
git clone https://github.com/TwoOfWands/Coders-Site-Django.git
cd Coders-Site-Django
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### Windows

```bash
venv\Scripts\activate
```

### Linux / macOS

```bash
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root:

```env
SECRET_KEY=your-secret-key
DEBUG=True

DATABASE_URL=

EMAIL_HOST_USER=your-email
EMAIL_HOST_PASSWORD=your-email-password

TURNSTILE_SITE_KEY=your-turnstile-site-key
TURNSTILE_SECRET_KEY=your-turnstile-secret-key

RECAPTCHA_SITE_KEY=your-recaptcha-site-key
RECAPTCHA_SECRET_KEY=your-recaptcha-secret-key
```

When `DATABASE_URL` is not provided, the project falls back to SQLite.

For PostgreSQL, configure `DATABASE_URL` with your PostgreSQL connection string.

### 5. Apply migrations

```bash
python manage.py migrate
```

### 6. Create an admin account

```bash
python manage.py createsuperuser
```

### 7. Run the development server

```bash
python manage.py runserver
```

Open:

```text
http://127.0.0.1:8000/
```

## 🔧 Useful URLs

```text
/                       Homepage
/course/list/           Course list
/course/categories/     Course categories
/instructor/list/       Instructor list
/instructor/dashboard/  Instructor dashboard
/dashboard/             Student dashboard
/blog/                  Blog
/faq/                   FAQ and community questions
/contact/               Contact form
/admin-1389/            Django admin
/sitemap.xml            XML sitemap
/robots.txt             Robots file
/rss/blog/              Blog RSS feed
/rss/course/            Course RSS feed
```

## 🔒 Production Notes

Before deploying to production:

* Set `DEBUG=False`
* Use a strong `SECRET_KEY`
* Configure `DATABASE_URL`
* Configure email credentials
* Configure reCAPTCHA and Turnstile keys
* Run:

```bash
python manage.py collectstatic
```

* Use Gunicorn or another production WSGI server
* Never commit secrets or credentials to Git

## 📜 License

This project is licensed under the **MIT License**.

## 👨‍💻 Author

**TwoOfWands**

GitHub:

https://github.com/TwoOfWands/Coders-Site-Django

---

<p align="center">
  Built with ❤️ using Django
</p>
