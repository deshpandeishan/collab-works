# CollabWorks

CollabWorks is a Flask-based web application designed to connect clients with freelancers through role-based discovery and direct communication. The application provides authentication for two distinct user types, internal messaging, role prediction using a machine learning model, and basic profile discovery.

The system is implemented as a monolithic Flask application with modular routing and server-rendered templates.

## Application Overview

The application supports two primary user roles:
- Clients
- Freelancers

Users authenticate via Flask-Login and interact with the platform through role-specific dashboards and shared messaging infrastructure.

## Core Components

### Authentication and User Management

- Uses `Flask-Login` for session management
- Supports multiple user models (`Client`, `Freelancer`)
- Dynamic user loading based on user ID and model type
- Role-based access control enforced at route level

### Messaging System

- Conversation-based internal chat system
- Conversations are grouped using a `conv_id`
- Messages are persisted using SQLAlchemy
- Supports:
  - Client → Freelancer conversations
  - Freelancer → Client conversations
- Message metadata includes sender, receiver, timestamp, and ownership flag

#### Message Model
- `conv_id` identifies a conversation thread
- Messages are retrieved and rendered per user context
- Server-generated responses supported for testing/demo purposes

### Chat Interfaces

- Separate chat views for clients and freelancers
- Conversation lists are dynamically built from stored messages
- Active conversation context is rendered server-side
- Messages can also be fetched asynchronously via JSON endpoints

### Role Prediction (Machine Learning)

- Uses pre-trained models loaded via `joblib`
- Models include:
  - Multi-label classifier
  - Label binarizer
  - Per-role probability thresholds
- Accepts free-text need statements
- Predicts up to N relevant freelancer roles
- Filters low-confidence and generic predictions
- Persists prediction history to a JSON file for later retrieval

### Freelancer Discovery

- Exposes a JSON endpoint for retrieving freelancer profiles
- Profiles include:
  - Name
  - Username
  - Tagline
  - Location
  - Hourly rate (derived)
  - Rating (derived)
- Profile images are assigned dynamically based on gender
- Intended for frontend-driven listing and search

### Client Status Validation

- Provides a lightweight endpoint to verify client authentication state
- Used for frontend gating and conditional rendering

## Routing Overview

The application exposes routes for:
- Authentication (via registered blueprints)
- Messaging and chat navigation
- Role prediction and retrieval
- Freelancer discovery
- Static informational pages
- Dashboard rendering

Blueprints are used to separate:
- Client-specific routes
- Freelancer-specific routes

## Technology Stack

### Backend
- Python 3.12
- Flask
- Flask-Login
- Flask-SQLAlchemy
- Flask-Bcrypt
- SQLite (primary datastore)
- Joblib (ML model loading)

### Frontend
- Server-rendered HTML templates (Jinja2)
- Vanilla JavaScript
- Static CSS assets

## Data Storage

- SQLite database used via SQLAlchemy ORM
- Direct SQLite queries used for specific dashboard views
- JSON file used for persisting role prediction history

## Execution Model

- Runs as a single Flask application
- Synchronous request handling
- ML inference performed inline during request processing

## Notes

- Client and Freelancer are treated as separate user models
- Messaging logic assumes a shared conversation namespace
- Role prediction is best-effort and threshold-based
- The application is designed for incremental extension rather than horizontal scaling
