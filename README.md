# SocialText

A lightweight, text-based social media platform built with Python (Flask) and deployed on Microsoft Azure App Service.

## What it does

SocialText lets users connect, share short posts, and interact with each other through likes and comments. The platform has two distinct access levels: a standard user experience and an admin control panel.

### User features
- Register an account with a unique username and email address
- Log in using either your username or email
- Write posts visible to everyone (public) or only to friends
- Browse the public feed or a personalized friends-only feed
- Like and comment on posts
- Send, accept, and decline friend requests
- Unfriend users at any time

### Admin features
- View platform statistics (total users, posts, comments, friendships)
- Promote any user to admin or demote any admin to a regular user
- Delete any user account or post

### Design
- Clean, minimal interface with no unnecessary clutter
- Light and dark mode, persisted across sessions
- Works on desktop and mobile browsers

## Tech stack

| Layer    | Technology                        |
|----------|-----------------------------------|
| Backend  | Python 3.11, Flask                |
| Database | Azure SQL Database (via pyodbc)   |
| Auth     | Flask-Login, Werkzeug             |
| Hosting  | Azure App Service (Linux, PaaS)   |
| Frontend | Server-rendered Jinja2 templates  |

## Notes

- The first account registered on a fresh deployment is automatically granted admin privileges.
- Login accepts both username and email address.
- Email addresses are validated on registration and must be unique per account.
