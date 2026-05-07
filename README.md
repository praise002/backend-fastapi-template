# Production-Ready FastAPI Backend Template

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A feature-rich, scalable, and production-ready template for building robust FastAPI backends. This template incorporates best practices for project structure, authentication, database management, and deployment, allowing you to kickstart your next project with a solid foundation.

## Core Features

-   **Modern Tech Stack:** Python 3.11+, FastAPI, Pydantic v2, and SQLAlchemy 2.0.
-   **Authentication:** Secure JWT (Access & Refresh) token implementation with OTP and OAuth2 (Google) support.
-   **Database:** Async support for PostgreSQL with Alembic for database migrations.
-   **Rate Limiting:** Pre-configured endpoint rate limiting using `slowapi`.
-   **Email Integration:** Async email sending with `mjml-python` for responsive HTML templates.
-   **Containerization:** Multi-stage Dockerfile for lightweight, production-optimized images.
-   **CI/CD Ready:** Includes configurations for Railway and GitHub Actions.
-   **Organized Structure:** Domain-based project structure for scalability and maintainability.
-   **Tooling:** `Makefile` for easy access to common commands (run, test, lint).

## Getting Started

Follow these steps to get your local development environment up and running.

### Prerequisites

-   Python 3.11+
-   Docker and Docker Compose
-   An `.env` file (use the `.env.example` as a guide)

### Installation

1.  **Clone the repository:**
    ```bash
    git clone <your-repo-url>
    cd backend-fastapi-template
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements/dev.txt
    ```

4.  **Launch services with Docker:**
    This will start the PostgreSQL database and Redis.
    ```bash
    docker-compose up -d
    ```

5.  **Run database migrations:**
    ```bash
    make migrate
    ```

6.  **Run the development server:**
    ```bash
    make dev
    ```
    The API will be available at `http://localhost:8000`.


## 🏗️ Project Structure

This project follows **Onion Architecture** with a **modular structure** to ensure:
- **Separation of Concerns**: Each layer has a single responsibility
- **Testability**: Easy to mock dependencies at each layer
- **Scalability**: Modules can be developed and deployed independently
- **Maintainability**: Clear dependency flow (inward-only)
  
TODO: Complete this section later. The project structure is currently being refined.

## Usage

This template uses a `Makefile` to simplify common development tasks.

-   **Run the development server:**
    ```bash
    make dev
    ```
-   **Run tests:**
    ```bash
    make test
    ```
-   **Run linter and formatter:**
    ```bash
    make lint
    ```
-   **Apply database migrations:**
    ```bash
    make migrate
    ```
-   **Create a new migration:**
    ```bash
    make migration-new message="Your migration message"
    ```

## Deployment

This template is configured for easy deployment on platforms that support Docker.

-   **Docker:** A multi-stage `Dockerfile` is included to build a small, secure production image.
-   **Railway:** A `railway.json` file is provided for one-click deployments on Railway.
-   **Digital Ocean:** The Docker setup is compatible with Digital Ocean Apps and other container-based hosting services.

## Further Reading & Resources

This template was built upon the excellent work and advice from the community. Here are some of the resources that informed its structure and features.

### Best Practices & Tips

-   [fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices/blob/master/README.md): The original inspiration for this template's structure and conventions.
-   [101 FastAPI Tips](https://github.com/Kludex/fastapi-tips/blob/main/README.md): A collection of valuable tips and tricks for working with FastAPI.

### Key Libraries

-   [slowapi](https://github.com/laurentS/slowapi): The library used for rate limiting.
-   [mjml-python](https://github.com/mgd020/mjml-python/blob/master/README.md): For creating responsive HTML emails with Python.

### Testing

-   [Python Testcontainers for Integration Testing](https://oneuptime.com/blog/post/2025-01-06-python-testcontainers-integration/view): A guide on using Testcontainers for reliable integration tests.
-   [Example Login Tests](https://github.com/Kludex/fastapi-microservices/blob/main/users/tests/test_login.py): A practical example of testing authentication endpoints.

### Deployment & Docker

-   [Dockerize FastAPI for Development and Production](https://python.plainenglish.io/dockerize-fastapi-for-development-and-production-4a2adfd722f2): A guide to containerizing your FastAPI application.
-   [FastAPI Docker Best Practices](https://betterstack.com/community/guides/scaling-python/fastapi-docker-best-practices/): Tips for creating optimized and secure Docker images.
-   [Deploy FastAPI to Railway with Dockerfile](https://www.codingforentrepreneurs.com/blog/deploy-fastapi-to-railway-with-this-dockerfile): A tutorial for deploying on the Railway platform.
-   [Deploying FastAPI to Digital Ocean Apps](https://ashaya.medium.com/deploying-fast-api-to-digital-ocean-apps-d8b4a886a7a9): A walkthrough for deploying on Digital Ocean.


