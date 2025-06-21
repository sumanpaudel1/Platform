
# 🛍️ Smart Multi-Vendor E-Commerce Platform

A subscription-based, AI-powered multi-vendor e-commerce solution built using Django. This platform empowers small and medium businesses to quickly launch customizable online stores with built-in tools like product management, order handling, eSewa payments, image-based product search, recommendations, and virtual try-on features.

---

## 📌 Features

### 🧑‍💼 For Vendors:
- Personalized store with a subdomain (e.g., `store.yourdomain.com`)
- Vendor dashboard to manage:
  - Products
  - Orders & delivery status
  - Discounts & coupons
  - Sales analytics
- Store customization (logos, colors, branding)
- Google login support
- Subscription-based access (Admin approval required)

### 👥 For Customers:
- Browse multiple vendor stores
- Image-based product search (CLIP + Pinecone)
- AI-driven product recommendations
- Virtual try-on experience using VITON-HD
- Secure checkout via eSewa or Cash on Delivery
- Order tracking, cart management, and saved addresses

---

## 🧠 AI Services

- **Image Search**: Find visually similar items via CLIP + Pinecone.
- **Recommendation System**: Personalized suggestions based on browsing and purchase history.
- **Virtual Try-On**: Try on clothing virtually using a model and the VITON-HD system hosted on Google Colab via Flask API.

---

## 🔧 Technologies Used

| Component          | Stack / Tool |
|-------------------|--------------|
| Backend           | Django (Python) |
| Frontend          | Django Templates, HTML, Tailwind CSS, JavaScript |
| Database          | MySQL, Pinecone (vector DB) |
| AI Models         | CLIP, VITON-HD, Content-based recommender |
| Payment Gateway   | eSewa (Nepal) |
| Dev Tools         | VS Code, Git, GitHub |
| Version Control   | GitHub |
| Deployment        | (add your deployment link here, if available) |

---

## 📦 Setup Instructions

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/multi-vendor-ecommerce.git
cd multi-vendor-ecommerce
```

### 2. Create a Virtual Environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Requirements
```bash
pip install -r requirements.txt
```

### 4. Set Up the Database
Make sure MySQL is running. Then create a new database and update the credentials in `settings.py`.

```sql
CREATE DATABASE ecommerce_db;
```

### 5. Migrate and Seed
```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser  # Create admin
```

### 6. Run the Server
```bash
python manage.py runserver
```

---

## 🧪 Testing Summary

Manual testing was conducted across modules:
- ✅ User & Vendor registration/login (including Google OAuth)
- ✅ OTP email verification
- ✅ Vendor subdomain creation
- ✅ Product CRUD and categorization
- ✅ Order management (status tracking, updates)
- ✅ Checkout & Payment (eSewa & COD)
- ✅ AI services: image search, recommendation, and virtual try-on

Refer to `/docs/testing` for full test cases.

---

## 📊 Project Management

- Methodology: **SCRUM**
- Sprints covered:
  1. Project setup
  2. Core e-commerce modules
  3. Payment integration
  4. AI features
  5. UI/UX Enhancements
  6. Final testing and deployment

Gantt chart and log sheet available in `docs/`.

---

## 📚 Academic Focus

### Key Research Questions:
1. **How can a subscription-based multi-vendor e-commerce platform help small businesses transition from social media selling to structured platforms?**
2. **What AI features improve product discovery and user satisfaction in small-scale online marketplaces?**

Detailed discussion available in the full [project report](./docs/Final_Report.pdf).

---

## 🚀 Future Improvements

- Add support for other payment gateways (e.g., Khalti, Stripe)
- Improve virtual try-on accuracy with diverse body types
- Introduce automated email confirmation system
- Expand AI recommendation system with collaborative filtering

---

## 👨‍🎓 Author

**Suman Paudel**  
University of Wolverhampton  
Email: [official.sumanpaudel@gmail.com](mailto:official.sumanpaudel@gmail.com)

Project supervised by: Nikunja Lamsal

---

## 📄 License

This project is for academic and educational purposes. Contact the author for reuse permissions.
