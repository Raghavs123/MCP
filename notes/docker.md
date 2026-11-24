# Docker

- Use a slim base image, for example python:3.12-slim.
- Multi-stage builds keep the final image small.
- Add a .dockerignore so .venv and .git never enter the image.
- Do not run the app as root: create a user.
