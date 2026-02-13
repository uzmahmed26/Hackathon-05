@echo off
echo Testing Docker setup for Customer Success AI Agent...

echo Building the project containers...
docker-compose build

echo Starting services in detached mode...
docker-compose up -d

echo Waiting for services to start...
timeout /t 30 /nobreak

echo Checking running containers...
docker-compose ps

echo To view logs, run: docker-compose logs -f
echo To stop services, run: docker-compose down