FROM python:3.11

ENV PYTHONUNBUFFERED 1

RUN mkdir /code
WORKDIR /code

COPY requirements.txt requirements-dev.txt /code/
RUN pip install -r requirements-dev.txt

COPY . /code/

# Command to run the Django development server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
