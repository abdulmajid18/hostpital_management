# Hospital Backend System

## Overview

This backend system is designed for a hospital to manage user signups, patient-doctor assignments, doctor note submissions, and dynamic scheduling of actionable steps based on live LLM (Language Model) processing. The system ensures secure handling of sensitive data and integrates a live LLM to extract actionable steps, which are divided into a checklist (immediate tasks) and a plan (scheduled actions). New note submissions cancel existing actionable steps and create new ones.

## Key Features

### User Management:
- User signup with roles (Patient or Doctor).
- Secure authentication using JWT (JSON Web Tokens).
- Password storage using bcrypt hashing.
- End-to-end encryption for patient notes using AES-256.

### Patient-Doctor Assignment:
- Patients can choose from a list of available doctors.
- Doctors can view their assigned patients.

### Doctor Notes & Actionable Steps:
- Doctors submit notes for patients.
- Notes are processed by an LLM to extract actionable steps:
  - **Checklist**: Immediate one-time tasks (e.g., buy medication).
  - **Plan**: Scheduled actions (e.g., daily reminders to take medication).
- Dynamic scheduling of reminders based on the plan.

### Dynamic Scheduling:
Supports three types of schedules:
1. **Fixed-Time**: Reminders at specific times (e.g., 10:00 AM).
2. **Interval-Based**: Reminders at regular intervals (e.g., every 6 hours).
3. **Frequency-Based**: Reminders a certain number of times per day (e.g., 3 times a day).
- **Adaptive reminders**: If a patient misses a reminder, the schedule adjusts to ensure all tasks are completed.

### API Endpoints:
- User signup, authentication, and role-based access.
- Patient-doctor assignment and management.
- Note submission, actionable step generation, and reminder scheduling.

## Technology Stack

### Authentication & Security:
- **JWT**: Stateless authentication for scalability.
- **bcrypt**: Secure password hashing.
- **AES-256**: End-to-end encryption for patient notes.

### Data Storage:
- **MongoDB**: Stores patient notes, doctor notes, and scheduling states. Chosen for its flexibility with unstructured data.
- **PostgreSQL**: Stores user management data (e.g., credentials, roles). Chosen for its robustness and ACID compliance.
- **Elasticsearch**: Integrated for future full-text search capabilities.
- **Redis**: Manages notifications and stores the state of actionable steps. Chosen for its fast, in-memory data storage.

### LLM Integration & Asynchronous Processing:
- **RabbitMQ**: Handles asynchronous processing of LLM tasks. Decouples note submission from LLM processing for scalability.

### Scheduling Strategy:
- **Dynamic Scheduling**: Adaptive reminders based on actionable steps extracted from notes.
- **State Management**: MongoDB for persistent storage, Redis for fast retrieval of next occurrences.

## Architecture Flow

### User Signup & Authentication:
- Users register with their details and role (Patient or Doctor).
- Passwords are hashed using bcrypt and stored in PostgreSQL.
- JWT tokens are issued for authenticated requests.

### Patient-Doctor Assignment:
- Patients select a doctor from the available list.
- Doctors can view their assigned patients.

### Note Submission & Actionable Steps:
- Doctors submit notes for patients.
- Notes are sent to RabbitMQ for asynchronous processing by the LLM.
- The LLM extracts actionable steps (checklist and plan) and stores them in MongoDB.

### Dynamic Scheduling:
- Reminders are scheduled based on the actionable steps.
- Redis stores the next occurrence of reminders for quick retrieval.
- If a patient misses a reminder, the schedule adjusts to ensure all tasks are completed.

### Notification Handling:
- Due reminders are retrieved from Redis and sent to patients.
- Patients can check in to mark reminders as completed.

## Future Improvements

- **Time Zone Support**: Add support for patient-specific time zones for reminders.
- **Enhanced Error Handling**: Provide detailed error messages for better debugging.
- **Rate Limiting**: Implement rate limiting on authentication endpoints to prevent brute-force attacks.
- **Testing**: Thoroughly test all schedule types and edge cases.

## Documentation

For detailed documentation, including API endpoints, design decisions, and technical constraints, refer to the Full Documentation [here](https://docs.google.com/document/d/1DUdAqUbmtqCIlMk-P8JyzLILUPOdVdHXsJtBSE8H5ys/edit?usp=sharing).

## Conclusion

This backend system is designed to handle the complex requirements of a hospital, ensuring secure data handling, scalable user management, and dynamic scheduling of actionable steps. By leveraging technologies like JWT, bcrypt, AES-256, MongoDB, PostgreSQL, Redis, RabbitMQ, and Elasticsearch, the system is well-equipped to meet current needs while being prepared for future growth.

## How to Use

1. Clone the repository.
2. Set up the required databases (MongoDB, PostgreSQL, Redis).
3. Configure environment variables (e.g., JWT secret, database credentials).
4. Run the application using your preferred backend stack (Node.js recommended).

## Contribution

Contributions are welcome! Please fork the repository and submit a pull request with your changes.

## License

This project is licensed under the MIT License. See the LICENSE file for details.
