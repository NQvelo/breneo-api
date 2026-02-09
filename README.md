## 🧠 Project Overview

BRENE01 is a Django REST API project that provides user management, media uploads,
and machine learning–based predictions using a pre-trained model.
The backend is designed to be scalable and easily integrated with frontend
applications such as React.



## 📁 Project Structure

```text
BRENE01/
├── .venv/                     # Python virtual environment
├── app/                       # Main Django application
│   ├── __pycache__/            # Python cache files
│   ├── management/             # Custom Django management commands
│   ├── migrations/             # Database migrations
│   ├── ml/                     # Machine Learning models & scripts
│   │   └── model.pkl           # Serialized ML model
│   ├── __init__.py             # Python package marker
│   ├── admin.py                # Django admin configuration
│   ├── apps.py                 # App configuration
│   ├── models.py               # Database models
│   ├── serializers.py          # DRF serializers
│   ├── tests.py                # Unit tests
│   ├── urls.py                 # App-level routing
│   └── views.py                # API / business logic
│
├── media/                      # Uploaded media files
│   └── profile_pics/           # User profile pictures
│
├── mysite/                     # Django project configuration
│   ├── __pycache__/            # Python cache files
│   ├── __init__.py             # Python package marker
│   ├── asgi.py                 # ASGI configuration
│   ├── settings.py             # Django settings
│   ├── urls.py                 # Project-level routing
│   └── wsgi.py                 # WSGI configuration
│
├── staticfiles/                # Collected static files
│   ├── admin/                  # Django admin static assets
│   └── rest_framework/         # DRF static assets
│
├── .env                        # Environment variables
├── .gitignore                  # Git ignore rules
├── db.sqlite3                  # SQLite database
├── manage.py                   # Django management script
├── Procfile                    # Deployment configuration
└── requirements.txt            # Python dependencies
```





## 📦 Dependencies

This project relies on the following key libraries and tools:

- Django & Django REST Framework for backend API development
- Authentication using dj-rest-auth, django-allauth, and JWT
- Machine Learning with scikit-learn, NumPy, Pandas
- Media handling with Cloudinary and Pillow
- Email services powered by SendGrid
- Database support with SQLite (development) and PostgreSQL (production)
- Deployment using Gunicorn and WhiteNoise
- Environment variable management with python-dotenv and python-decouple

For the full list of dependencies, see `requirements.txt`.


## ⚙️ Installation & Setup

**Python version:** Use **Python 3.11 or 3.12**. Python 3.14 is not yet supported by scipy/scikit-learn binary wheels (install would require a Fortran compiler).

```bash
git clone https://github.com/gaga-chituashvili/breneo.git

# Use Python 3.11 or 3.12 (e.g. pyenv install 3.12 && pyenv local 3.12)
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
