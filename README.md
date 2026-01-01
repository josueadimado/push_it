# Push-it Platform

A Django-based influencer marketing platform that connects brands with content creators for video promotion campaigns.

## Features

### For Brands
- Create and manage video promotion campaigns
- Wallet system for campaign payments
- Multi-currency support
- Campaign analytics and tracking
- Automated influencer matching

### For Influencers
- Profile management with platform verification
- Job feed with automatic matching
- Wallet system with withdrawal requests
- Multi-currency support
- Payment methods (Bank Transfer, Mobile Money)
- Notification system

### Platform Features
- OAuth integration for Instagram, Facebook, YouTube, TikTok
- Follower verification system
- Payment processing via Paystack
- Admin dashboard for operations
- Email notifications

## Tech Stack

- **Backend**: Django 6.0
- **Database**: SQLite (development), PostgreSQL (production recommended)
- **Payment**: Paystack API
- **Authentication**: Django's built-in auth system
- **Frontend**: HTML, CSS, JavaScript (Bootstrap Icons, Iconify)

## Installation

### Prerequisites
- Python 3.10+
- pip
- Virtual environment (recommended)

### Setup Steps

1. **Clone the repository**
   ```bash
   git clone <your-repo-url>
   cd Push_it
   ```

2. **Create and activate virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables**
   ```bash
   cp env.template .env
   # Edit .env with your actual credentials
   ```

5. **Run migrations**
   ```bash
   python manage.py migrate
   ```

6. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

7. **Run development server**
   ```bash
   python manage.py runserver
   ```

## Environment Variables

See `env.template` for all required environment variables. Key variables include:

- `DJANGO_SECRET_KEY`: Django secret key (change in production!)
- `DEBUG`: Set to `False` in production
- `EMAIL_*`: Email configuration for notifications
- `PAYSTACK_SECRET_KEY` & `PAYSTACK_PUBLIC_KEY`: Payment gateway keys
- `YOUTUBE_API_KEY`: For YouTube follower verification
- `INSTAGRAM_ACCESS_TOKEN` & `FACEBOOK_APP_ID`: For Instagram/Facebook verification

## Project Structure

```
Push_it/
├── accounts/          # User authentication and profiles
├── brands/            # Brand management and verification
├── influencers/      # Influencer profiles and verification
├── campaigns/         # Campaign creation and management
├── payments/          # Payment processing (Paystack)
├── operations/        # Admin operations and notifications
├── core/              # Core views and utilities
├── templates/         # HTML templates
├── static/            # Static files (CSS, JS, images)
└── pushit/            # Django project settings
```

## Deployment to PythonAnywhere

### Initial Setup

1. **Create a PythonAnywhere account** at https://www.pythonanywhere.com

2. **Open a Bash console** in PythonAnywhere

3. **Clone your repository**
   ```bash
   git clone https://github.com/yourusername/push-it.git
   cd push-it
   ```

4. **Create virtual environment**
   ```bash
   python3.10 -m venv venv
   source venv/bin/activate
   ```

5. **Install dependencies**
   ```bash
   pip install --user -r requirements.txt
   ```

6. **Set up environment variables**
   - Go to Files tab → Create `.env` file in your project directory
   - Copy contents from `env.template` and fill in production values
   - Set `DEBUG=False` and use a strong `SECRET_KEY`

7. **Run migrations**
   ```bash
   python manage.py migrate
   ```

8. **Create superuser**
   ```bash
   python manage.py createsuperuser
   ```

9. **Collect static files**
   ```bash
   python manage.py collectstatic --noinput
   ```

### Web App Configuration

1. **Go to Web tab** in PythonAnywhere dashboard

2. **Create a new web app** (if not exists)
   - Choose "Manual configuration"
   - Select Python 3.10

3. **Edit WSGI file**
   - Click on the WSGI configuration file link
   - Replace the content with:
   ```python
   import os
   import sys

   # Add your project directory to the path
   path = '/home/yourusername/push-it'
   if path not in sys.path:
       sys.path.insert(0, path)

   # Set environment variables
   os.environ['DJANGO_SETTINGS_MODULE'] = 'pushit.settings.prod'

   # Activate virtual environment
   activate_this = '/home/yourusername/push-it/venv/bin/activate_this.py'
   with open(activate_this) as file_:
       exec(file_.read(), dict(__file__=activate_this))

   from django.core.wsgi import get_wsgi_application
   application = get_wsgi_application()
   ```

4. **Configure Static Files**
   - In Web tab, scroll to "Static files"
   - Add mapping:
     - URL: `/static/`
     - Directory: `/home/yourusername/push-it/staticfiles/`
   - Add mapping:
     - URL: `/media/`
     - Directory: `/home/yourusername/push-it/media/`

5. **Set ALLOWED_HOSTS**
   - In your `.env` file or `pushit/settings/prod.py`:
   ```python
   ALLOWED_HOSTS = ['yourusername.pythonanywhere.com']
   ```

6. **Reload web app**
   - Click the green "Reload" button in Web tab

### Database Setup (Optional - for production)

For production, consider using MySQL (free on PythonAnywhere) or PostgreSQL:

1. **Create MySQL database** in Databases tab
2. **Update settings/prod.py**:
   ```python
   DATABASES = {
       'default': {
           'ENGINE': 'django.db.backends.mysql',
           'NAME': 'yourusername$pushit',
           'USER': 'yourusername',
           'PASSWORD': 'your-db-password',
           'HOST': 'yourusername.mysql.pythonanywhere-services.com',
       }
   }
   ```
3. **Install MySQL client**:
   ```bash
   pip install --user mysqlclient
   ```

### Scheduled Tasks (Optional)

For periodic tasks (e.g., sending notifications), use PythonAnywhere's Tasks tab:
- Set up a daily task to run: `python manage.py your_management_command`

## Development

### Running Tests
```bash
python manage.py test
```

### Creating Migrations
```bash
python manage.py makemigrations
python manage.py migrate
```

### Creating Management Commands
Management commands are in each app's `management/commands/` directory.

## Security Notes

- Never commit `.env` file to git
- Use strong `SECRET_KEY` in production
- Set `DEBUG=False` in production
- Use HTTPS in production
- Keep dependencies updated

## License

[Your License Here]

## Support

For issues and questions, please open an issue on GitHub.
