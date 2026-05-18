# NovaEdge Finance - Full Stack Application

A comprehensive cryptocurrency investment platform with user authentication, wallet management, investment plans, referral system, and real-time market data.

---

## 📋 Table of Contents

- [Project Overview](#project-overview)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
  - [Backend Setup (Django)](#backend-setup-django)
  - [Frontend Setup (React + Vite)](#frontend-setup-react--vite)
- [Database Setup](#database-setup)
  - [PostgreSQL (Development)](#postgresql-development)
  - [MariaDB/MySQL (Production)](#mariadbmysql-production)
- [Environment Variables](#environment-variables)
- [Initial Data Setup](#initial-data-setup)
  - [Creating Superuser](#creating-superuser)
  - [Creating Investment Plans](#creating-investment-plans)
- [Email Configuration](#email-configuration)
  - [cPanel SMTP Setup](#cpanel-smtp-setup)
  - [DNS Records (SPF, DKIM, DMARC)](#dns-records-spf-dkim-dmarc)
- [Deployment](#deployment)
  - [Backend (cPanel)](#backend-cpanel)
  - [Frontend (Vercel/Netlify/cPanel)](#frontend-vercelnetlifycpanel)
  - [HTTPS & Domain Setup](#https--domain-setup)
- [API Endpoints](#api-endpoints)
- [Payment Integration](#payment-integration)
  - [NOWPayments Setup](#nowpayments-setup)
  - [Webhook Configuration](#webhook-configuration)
- [Features](#features)
- [Troubleshooting](#troubleshooting)
- [License](#license)

---

## Project Overview

NovaEdge Finance is a full-stack cryptocurrency investment platform that allows users to:

- Register and verify their email
- Complete investment profiles
- Browse and invest in crypto investment plans
- Deposit funds via cryptocurrency (BTC, ETH, USDT, BNB)
- Track portfolio performance with real-time charts
- Earn referral bonuses
- View real-time market data via TradingView

---

## Tech Stack

### Frontend

- **React 18** with **Vite**
- **Tailwind CSS** for styling
- **shadcn/ui** component library
- **TradingView Widget** for real-time charts
- **Axios** for API requests

### Backend

- **Django 4.2** (Python 3.11+)
- **Django REST Framework** for API
- **SimpleJWT** for authentication
- **MariaDB/MySQL** for production database
- **PostgreSQL** for development database
- **NOWPayments** for crypto payment processing

---

## Project Structure

```
novaedgefinance_backend/          # Django Backend
├── authentication/               # User auth, profiles, verification
├── wallet/                       # Wallet, deposits, transactions
├── investments/                  # Investment plans, user investments
├── referrals/                    # Referral system, bonus wallet
├── notifications/                # User notifications
├── reporting/                    # Ledger, reports
├── core/                         # Core utilities, management
├── config/                       # Django settings, URLs, WSGI
├── requirements.txt              # Python dependencies
└── manage.py                     # Django management

novaedgefinance_frontend/         # React Frontend
├── src/
│   ├── components/               # Reusable components
│   │   ├── auth/                 # Login, Register, Verify Email
│   │   ├── dashboard/            # Dashboard overview, layouts
│   │   ├── profile/              # Profile, Security, Referrals
│   │   ├── wallet/               # Wallet, Deposit, Transactions
│   │   └── investments/          # Investment plans, charts
│   ├── hooks/                    # Custom React hooks
│   ├── app/                      # Page components
│   └── lib/                      # Utility functions
├── public/                       # Static assets
└── .htaccess                     # Apache config (cPanel deployment)
```

---

## Prerequisites

- **Python 3.11+**
- **Node.js 18+**
- **npm** or **yarn**
- **PostgreSQL** (development) or **MariaDB/MySQL** (production)
- **cPanel** hosting (for production deployment)
- **Git**

---

## Installation & Setup

### Backend Setup (Django)

```bash
# 1. Clone the repository
git clone https://github.com/its-jedu/novaedgefinance_backend.git
cd novaedgefinance_backend

# 2. Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file (see Environment Variables section)
cp .env.example .env
nano .env  # Edit with your settings

# 5. Run migrations
python manage.py migrate

# 6. Create superuser
python manage.py createsuperuser

# 7. Create investment plans (see Initial Data Setup)

# 8. Run development server
python manage.py runserver
```

### Frontend Setup (React + Vite)

```bash
# 1. Clone the repository
git clone https://github.com/its-jedu/novaedgefinance_frontend.git
cd novaedgefinance_frontend

# 2. Install dependencies
npm install

# 3. Create .env file
echo "VITE_API_URL=http://localhost:8000" > .env

# 4. Run development server
npm run dev
```

---

## Database Setup

### PostgreSQL (Development)

```sql
-- Create database and user
CREATE DATABASE novaedge_db;
CREATE USER novaedge_user WITH PASSWORD 'your_password';
ALTER ROLE novaedge_user SET client_encoding TO 'utf8';
ALTER ROLE novaedge_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE novaedge_user SET timezone TO 'UTC';
GRANT ALL PRIVILEGES ON DATABASE novaedge_db TO novaedge_user;

-- Grant schema permissions
\c novaedge_db
GRANT ALL ON SCHEMA public TO novaedge_user;
```

**`.env` for PostgreSQL:**

```env
DB_NAME=novaedge_db
DB_USER=novaedge_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=5432
```

### MariaDB/MySQL (Production)

```sql
-- Create database and user
CREATE DATABASE novaedge_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'novaedge_user'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON novaedge_db.* TO 'novaedge_user'@'localhost';
FLUSH PRIVILEGES;
```

**`.env` for MariaDB:**

```env
DB_NAME=novaedge_db
DB_USER=novaedge_user
DB_PASSWORD=your_password
DB_HOST=localhost
DB_PORT=3306
```

---

## Environment Variables

Create a `.env` file in the backend root directory:

```env
# Django Settings
DEBUG=True  # Set to False in production
SECRET_KEY=your-secret-key-here
DJANGO_SETTINGS_MODULE=config.settings

# Database Configuration
DB_NAME=novaedge_db
DB_USER=novaedge_user
DB_PASSWORD=your-db-password
DB_HOST=localhost
DB_PORT=5432  # 3306 for MariaDB

# Site URLs
SITE_URL=https://api.novaedgefinance.com
FRONTEND_URL=https://novaedgefinance.com

# Allowed Hosts
ALLOWED_HOSTS=api.novaedgefinance.com,novaedgefinance.com,localhost,127.0.0.1

# CORS Settings
CORS_ALLOWED_ORIGINS=https://novaedgefinance.com,http://localhost:5173

# NOWPayments Configuration
NOWPAYMENTS_API_KEY=your-nowpayments-api-key
NOWPAYMENTS_IPN_SECRET=your-nowpayments-ipn-secret
NOWPAYMENTS_BASE_URL=https://api.nowpayments.io/v1

# Email Configuration (cPanel SMTP)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=novaedgefinance.com
EMAIL_PORT=465
EMAIL_USE_TLS=False
EMAIL_USE_SSL=True
EMAIL_HOST_USER=noreply@novaedgefinance.com
EMAIL_HOST_PASSWORD=your-email-password
DEFAULT_FROM_EMAIL=NovaEdge Finance <noreply@novaedgefinance.com>
SERVER_EMAIL=noreply@novaedgefinance.com

# Company Info
COMPANY_NAME=NovaEdge Finance
COMPANY_TAGLINE=Smart Crypto Investing Starts Here

# Security (set True in production)
SECURE_SSL_REDIRECT=False
SESSION_COOKIE_SECURE=False
CSRF_COOKIE_SECURE=False
SECURE_BROWSER_XSS_FILTER=True
SECURE_HSTS_SECONDS=0

# Admin Account
DJANGO_SUPERUSER_EMAIL=admin@novaedgefinance.com
DJANGO_SUPERUSER_PASSWORD=your-admin-password
DJANGO_SUPERUSER_FIRST_NAME=Admin
DJANGO_SUPERUSER_LAST_NAME=User
DJANGO_SUPERUSER_COUNTRY=USA
```

---

## Initial Data Setup

### Creating Superuser

```bash
# Method 1: Interactive
python manage.py createsuperuser

# Method 2: Using environment variables
python manage.py shell
```

```python
from django.contrib.auth import get_user_model
User = get_user_model()
User.objects.create_superuser(
    email='admin@novaedgefinance.com',
    password='your-password',
    first_name='Admin',
    last_name='User',
    country='USA'
)
```

### Creating Investment Plans

```bash
python manage.py shell
```

```python
from investments.models import InvestmentPlan
from decimal import Decimal

# Check existing plans
if InvestmentPlan.objects.count() == 0:
    # Starter Plan
    InvestmentPlan.objects.create(
        name='Starter Package',
        plan_type='STARTER',
        category='DUAL_STRATEGY',
        description='Perfect for beginners. Start your investment journey with our starter package.',
        short_description='Start with as little as $100',
        min_amount=Decimal('100.00'),
        max_amount=Decimal('5000.00'),
        min_return_multiplier=Decimal('5.00'),
        max_return_multiplier=Decimal('5.00'),
        return_period='WEEKLY',
        min_duration_days=7,
        max_duration_days=7,
        is_active=True,
        is_featured=True,
        display_order=1,
        risk_level='LOW'
    )

    # Growth Plan
    InvestmentPlan.objects.create(
        name='Growth Plan',
        plan_type='GROWTH',
        category='DUAL_STRATEGY',
        description='Balanced growth for medium-term investors.',
        short_description='Higher returns with moderate risk',
        min_amount=Decimal('250.00'),
        max_amount=Decimal('10000.00'),
        min_return_multiplier=Decimal('8.00'),
        max_return_multiplier=Decimal('8.00'),
        return_period='WEEKLY',
        min_duration_days=14,
        max_duration_days=14,
        is_active=True,
        is_featured=True,
        display_order=2,
        risk_level='MODERATE'
    )

    # Elite Plan
    InvestmentPlan.objects.create(
        name='Elite Plan',
        plan_type='PREMIUM',
        category='DUAL_STRATEGY',
        description='Premium plan for maximum returns.',
        short_description='Maximum returns with expert management',
        min_amount=Decimal('1000.00'),
        max_amount=Decimal('50000.00'),
        min_return_multiplier=Decimal('12.00'),
        max_return_multiplier=Decimal('12.00'),
        return_period='MONTHLY',
        min_duration_days=30,
        max_duration_days=30,
        is_active=True,
        is_featured=True,
        display_order=3,
        risk_level='HIGH'
    )

    print("✓ Investment plans created successfully!")
else:
    print(f"✓ {InvestmentPlan.objects.count()} plans already exist.")
```

---

## Email Configuration

### cPanel SMTP Setup

1. Log into **cPanel** → **Email Accounts**
2. Create email: `noreply@novaedgefinance.com`
3. Go to **Email Accounts** → **Connect Devices**
4. Note the SMTP settings:
   - **Outgoing Server:** `novaedgefinance.com`
   - **SMTP Port:** `465` (SSL) or `587` (TLS)
   - **Authentication:** Required

### DNS Records (SPF, DKIM, DMARC)

Add these TXT records to your domain DNS:

**SPF Record:**

```
Name: @ (or novaedgefinance.com)
Value: v=spf1 +mx +a +ip4:YOUR_SERVER_IP +include:spf.mysecurecloudhost.com ~all
```

**DKIM Record:**

```
Name: default._domainkey
Value: (Get this from cPanel → Email Deliverability → DKIM)
```

**DMARC Record:**

```
Name: _dmarc
Value: v=DMARC1; p=none
```

---

## Deployment

### Backend (cPanel)

```bash
# SSH into cPanel server
ssh user@yourserver.com

# Navigate to app directory
cd ~/novaedge_api

# Clone repository
git clone https://github.com/its-jedu/novaedgefinance_backend.git
cd novaedgefinance_backend

# Activate virtual environment
source ~/virtualenv/novaedge_api/3.11/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file with production settings
nano .env

# Run migrations
python manage.py migrate

# Create investment plans (if first deployment)
python manage.py shell
# (run the investment plans creation script above)

# Collect static files
python manage.py collectstatic --noinput

# Restart the app
touch ~/novaedge_api/passenger_wsgi.py
```

**cPanel Python App Configuration:**

- **Application root:** `/home/user/novaedge_api/novaedgefinance_backend`
- **Application URL:** `api.novaedgefinance.com`
- **Application startup file:** `passenger_wsgi.py`
- **Application Entry point:** `config.wsgi`

### Frontend (Vercel/Netlify/cPanel)

**Build the frontend:**

```bash
npm run build
```

**cPanel Deployment:**

1. Upload the `dist/` folder contents to `public_html/`
2. Add `.htaccess` file:

```apache
<IfModule mod_rewrite.c>
    RewriteEngine On
    RewriteBase /
    RewriteCond %{HTTPS} off
    RewriteRule ^(.*)$ https://%{HTTP_HOST}/$1 [L,R=301]
    RewriteCond %{HTTP_HOST} ^www\.novaedgefinance\.com [NC]
    RewriteRule ^(.*)$ https://novaedgefinance.com/$1 [L,R=301]
    RewriteCond %{REQUEST_FILENAME} !-f
    RewriteCond %{REQUEST_FILENAME} !-d
    RewriteRule ^(.*)$ /index.html [L,QSA]
</IfModule>
```

### HTTPS & Domain Setup

1. Install SSL certificate via cPanel → SSL/TLS
2. Point domain A records:
   - `novaedgefinance.com` → Server IP
   - `api.novaedgefinance.com` → Server IP
   - `www.novaedgefinance.com` → Server IP

---

## API Endpoints

### Authentication

| Method | Endpoint                         | Description               |
| ------ | -------------------------------- | ------------------------- |
| POST   | `/api/auth/register/`            | Register new user         |
| POST   | `/api/auth/login/`               | Login                     |
| POST   | `/api/auth/verify-email/`        | Verify email              |
| POST   | `/api/auth/resend-verification/` | Resend verification email |
| GET    | `/api/auth/profile/`             | Get user profile          |
| PUT    | `/api/auth/profile/`             | Update profile            |
| PUT    | `/api/auth/profile/investment/`  | Update investment profile |
| POST   | `/api/auth/change-password/`     | Change password           |
| POST   | `/api/auth/logout/`              | Logout                    |

### Wallet

| Method | Endpoint                                   | Description          |
| ------ | ------------------------------------------ | -------------------- |
| GET    | `/api/wallet/overview/`                    | Wallet overview      |
| POST   | `/api/wallet/deposits/create/`             | Create deposit       |
| GET    | `/api/wallet/deposits/my/`                 | My deposits          |
| GET    | `/api/wallet/deposits/status/?payment_id=` | Check deposit status |
| GET    | `/api/wallet/transactions/my/`             | My transactions      |
| GET    | `/api/wallet/plans/`                       | Investment plans     |

### Investments

| Method | Endpoint                                 | Description         |
| ------ | ---------------------------------------- | ------------------- |
| GET    | `/api/investments/plans/`                | All plans           |
| GET    | `/api/investments/investments/my/`       | My investments      |
| GET    | `/api/investments/investments/overview/` | Investment overview |
| POST   | `/api/investments/investments/start/`    | Start investment    |

### Referrals

| Method | Endpoint                         | Description        |
| ------ | -------------------------------- | ------------------ |
| GET    | `/api/referrals/my-code/`        | My referral code   |
| GET    | `/api/referrals/stats/`          | Referral stats     |
| GET    | `/api/referrals/my-referrals/`   | My referrals       |
| GET    | `/api/referrals/bonus-wallet/`   | Bonus wallet       |
| POST   | `/api/referrals/create-custom/`  | Create custom code |
| POST   | `/api/referrals/withdraw-bonus/` | Withdraw bonus     |

---

## Payment Integration

### NOWPayments Setup

1. Register at [NOWPayments](https://nowpayments.io/)
2. Get your **API Key** from Dashboard → API Keys
3. Set **IPN Secret Key** in Dashboard → Settings
4. Add to `.env`:
   ```env
   NOWPAYMENTS_API_KEY=your-api-key
   NOWPAYMENTS_IPN_SECRET=your-ipn-secret
   NOWPAYMENTS_BASE_URL=https://api.nowpayments.io/v1
   ```

### Webhook Configuration

In NOWPayments Dashboard → Settings → IPN:

- **IPN URL:** `https://api.novaedgefinance.com/api/wallet/nowpayments-webhook/`
- **Secret:** Same as `NOWPAYMENTS_IPN_SECRET`

---

## Features

### User Features

- ✅ Email registration & verification
- ✅ Secure JWT authentication
- ✅ Investment profile management
- ✅ Multiple investment plans
- ✅ Cryptocurrency deposits (BTC, ETH, USDT, BNB)
- ✅ Real-time portfolio tracking
- ✅ TradingView market charts
- ✅ Referral program with bonus wallet
- ✅ Transaction history
- ✅ Profile editing
- ✅ Password change

### Admin Features

- ✅ User management
- ✅ Investment plan management
- ✅ Deposit monitoring
- ✅ Transaction oversight
- ✅ Referral system administration
- ✅ Manual bonus crediting

### Security

- ✅ JWT token authentication
- ✅ Email verification required
- ✅ SSL/TLS encryption
- ✅ CORS protection
- ✅ CSRF protection
- ✅ Rate limiting
- ✅ Account lockout after failed attempts

---

## Troubleshooting

### Common Issues

**1. "ModuleNotFoundError: No module named 'django'"**

```bash
# Activate virtual environment
source venv/bin/activate  # Local
source ~/virtualenv/novaedge_api/3.11/bin/activate  # cPanel
```

**2. Database connection errors**

- Verify `.env` database credentials
- Check if database service is running
- Ensure user has proper permissions

**3. Email not sending**

- Verify SMTP settings in `.env`
- Check SPF/DKIM/DMARC DNS records
- Test via Django shell:
  ```python
  from django.core.mail import send_mail
  send_mail('Test', 'Test message.', 'noreply@novaedgefinance.com', ['your@email.com'], fail_silently=False)
  ```

**4. Static files not loading**

```bash
python manage.py collectstatic --noinput
```

**5. NOWPayments deposit issues**

- Verify API key is correct
- Check IPN secret matches NOWPayments dashboard
- Ensure webhook URL is accessible from internet

**6. Investment plans not showing**

- Run the investment plans creation script above
- Verify plans exist: `InvestmentPlan.objects.count()`

**7. Frontend routes return 404 on cPanel**

- Verify `.htaccess` file exists in `public_html/`
- Ensure `mod_rewrite` is enabled in cPanel

---

## Support

For support, email: support@novaedgefinance.com

---

**Built with ❤️ by JEDU**
