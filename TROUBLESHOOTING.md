# Customer Success AI Agent - Troubleshooting Guide

This guide provides solutions to common issues you may encounter when running the Customer Success AI Agent.

## Table of Contents
- [General Issues](#general-issues)
- [Database Issues](#database-issues)
- [Redis Issues](#redis-issues)
- [API Issues](#api-issues)
- [Channel Integration Issues](#channel-integration-issues)
- [Docker Issues](#docker-issues)
- [Performance Issues](#performance-issues)
- [Environment Issues](#environment-issues)

## General Issues

### Application won't start
**Symptoms**: Service fails to start or crashes immediately

**Solutions**:
1. Check logs for specific error messages:
   ```bash
   make logs
   ```
2. Verify all required environment variables are set:
   ```bash
   docker-compose exec api env | grep -E "(DATABASE_URL|REDIS_URL|HF_TOKEN)"
   ```
3. Ensure Docker has sufficient resources (at least 4GB RAM recommended)

### Health check fails
**Symptoms**: `/health` endpoint returns error or unhealthy status

**Solutions**:
1. Check if all services are running:
   ```bash
   docker-compose ps
   ```
2. Verify database connectivity:
   ```bash
   docker-compose exec postgres pg_isready
   ```
3. Verify Redis connectivity:
   ```bash
   docker-compose exec redis redis-cli ping
   ```

## Database Issues

### Cannot connect to PostgreSQL
**Symptoms**: Database connection errors, timeouts

**Solutions**:
1. Check if PostgreSQL is running:
   ```bash
   docker-compose ps | grep postgres
   ```
2. Verify database credentials in `.env` file
3. Check PostgreSQL logs:
   ```bash
   docker-compose logs postgres
   ```
4. Restart PostgreSQL service:
   ```bash
   docker-compose restart postgres
   ```

### Database schema not initialized
**Symptoms**: Table doesn't exist errors, migration failures

**Solutions**:
1. Run database initialization manually:
   ```bash
   make db-migrate
   ```
2. Check schema file exists and is readable:
   ```bash
   ls -la database/schema.sql
   ```
3. Verify database is empty and needs initialization:
   ```bash
   docker-compose exec postgres psql -U fte_user -d fte_db -c "\dt"
   ```

### Slow database queries
**Symptoms**: High response times, timeouts on database operations

**Solutions**:
1. Check active connections:
   ```bash
   docker-compose exec postgres psql -U fte_user -d fte_db -c "SELECT count(*) FROM pg_stat_activity;"
   ```
2. Look for long-running queries:
   ```bash
   docker-compose exec postgres psql -U fte_user -d fte_db -c "SELECT pid, now() - pg_stat_activity.query_start AS duration, query FROM pg_stat_activity WHERE (now() - pg_stat_activity.query_start) > interval '5 minutes';"
   ```
3. Add indexes to frequently queried columns

## Redis Issues

### Cannot connect to Redis
**Symptoms**: Redis connection errors, caching failures

**Solutions**:
1. Check if Redis is running:
   ```bash
   docker-compose ps | grep redis
   ```
2. Test Redis connectivity:
   ```bash
   docker-compose exec redis redis-cli ping
   ```
3. Check Redis logs:
   ```bash
   docker-compose logs redis
   ```
4. Restart Redis service:
   ```bash
   docker-compose restart redis
   ```

### Redis memory issues
**Symptoms**: Out of memory errors, evicted keys, performance degradation

**Solutions**:
1. Check Redis memory usage:
   ```bash
   docker-compose exec redis redis-cli info memory
   ```
2. Increase Redis memory limit in docker-compose.yml:
   ```yaml
   redis:
     command: redis-server --maxmemory 2gb --maxmemory-policy allkeys-lru
   ```
3. Check for memory leaks in application code
4. Implement proper cache expiration strategies

## API Issues

### API returns 500 errors
**Symptoms**: Server errors when making requests to API endpoints

**Solutions**:
1. Check API logs:
   ```bash
   make logs-api
   ```
2. Verify all required services are running:
   ```bash
   docker-compose ps
   ```
3. Check if API has proper environment variables:
   ```bash
   docker-compose exec api env
   ```
4. Test direct connectivity to dependencies:
   ```bash
   docker-compose exec api bash -c "curl -I http://postgres:5432"
   docker-compose exec api bash -c "curl -I http://redis:6379"
   ```

### API response times are too slow
**Symptoms**: High latency, timeouts

**Solutions**:
1. Check system resources:
   ```bash
   docker stats
   ```
2. Monitor API performance:
   ```bash
   docker-compose exec api top
   ```
3. Check for bottlenecks in database queries
4. Verify AI model API (HuggingFace/OpenAI) is responsive
5. Scale API instances if needed:
   ```bash
   docker-compose up -d --scale api=3
   ```

## Channel Integration Issues

### Gmail integration not working
**Symptoms**: Email queries not being processed, webhook errors

**Solutions**:
1. Verify Gmail credentials file exists:
   ```bash
   ls -la credentials/gmail_credentials.json
   ```
2. Check Gmail API permissions in Google Cloud Console
3. Verify webhook URL is accessible and properly configured
4. Check API logs for Gmail-specific errors:
   ```bash
   make logs-api | grep gmail
   ```

### WhatsApp integration not working
**Symptoms**: WhatsApp messages not being processed, webhook errors

**Solutions**:
1. Verify Twilio credentials are correct:
   ```bash
   docker-compose exec api env | grep TWILIO
   ```
2. Check Twilio Console for webhook delivery status
3. Verify webhook URL is properly configured in Twilio
4. Check API logs for WhatsApp-specific errors:
   ```bash
   make logs-api | grep whatsapp
   ```

### Webhook signature verification fails
**Symptoms**: Webhook requests rejected due to signature mismatch

**Solutions**:
1. Verify webhook signing secrets are correctly configured
2. Check if webhook URL uses HTTPS in production
3. Verify Twilio/Gmail is sending requests to the correct endpoint
4. Check for proxy/middleware that might alter request body

## Docker Issues

### Docker containers won't start
**Symptoms**: `docker-compose up` fails, containers crash immediately

**Solutions**:
1. Check Docker daemon is running:
   ```bash
   docker ps
   ```
2. Verify Docker has enough resources:
   ```bash
   docker system df
   ```
3. Check Docker logs:
   ```bash
   docker-compose logs
   ```
4. Clean Docker system:
   ```bash
   docker system prune -a
   ```

### Docker build fails
**Symptoms**: `docker-compose build` fails with compilation errors

**Solutions**:
1. Check Dockerfile syntax and dependencies
2. Verify base image exists and is accessible
3. Clear Docker build cache:
   ```bash
   docker builder prune
   ```
4. Check internet connectivity for downloading dependencies

### Insufficient disk space
**Symptoms**: Docker operations fail due to disk space issues

**Solutions**:
1. Check available disk space:
   ```bash
   df -h
   ```
2. Clean Docker system:
   ```bash
   docker system prune -a
   docker volume prune
   ```
3. Remove unused images:
   ```bash
   docker image prune -a
   ```

## Performance Issues

### High CPU usage
**Symptoms**: High CPU consumption, slow response times

**Solutions**:
1. Monitor CPU usage:
   ```bash
   docker stats
   ```
2. Profile application performance
3. Check for infinite loops or inefficient algorithms
4. Scale services horizontally:
   ```bash
   docker-compose up -d --scale worker=5
   ```

### High memory usage
**Symptoms**: Out of memory errors, application crashes

**Solutions**:
1. Monitor memory usage:
   ```bash
   docker stats
   ```
2. Check for memory leaks in application code
3. Increase container memory limits in docker-compose.yml
4. Optimize data structures and caching strategies

### Slow AI responses
**Symptoms**: Delays in AI-generated responses

**Solutions**:
1. Check HuggingFace/OpenAI API status
2. Verify API key has sufficient quota
3. Implement request caching where appropriate
4. Consider using smaller, faster models for initial responses

## Environment Issues

### Environment variables not loaded
**Symptoms**: Missing API keys, wrong configuration values

**Solutions**:
1. Verify `.env` file exists and has correct permissions:
   ```bash
   ls -la .env
   ```
2. Check that `.env` file is in the correct directory
3. Verify environment variables are accessible in containers:
   ```bash
   docker-compose exec api env | grep YOUR_VAR
   ```
4. Restart services after changing environment variables:
   ```bash
   make down && make up
   ```

### Permission denied errors
**Symptoms**: File access errors, inability to write logs

**Solutions**:
1. Check file permissions:
   ```bash
   ls -la
   ```
2. Ensure Docker is running with appropriate permissions
3. Verify volume mounts have correct ownership
4. Run Docker commands with proper user context

### Port conflicts
**Symptoms**: Services fail to start due to port already in use

**Solutions**:
1. Check which processes are using the ports:
   ```bash
   netstat -tulpn | grep :8000
   # On macOS/Windows:
   lsof -i :8000
   ```
2. Kill conflicting processes or change port configuration in docker-compose.yml
3. Use different ports for different environments

## Getting Help

If you encounter issues not covered in this guide:

1. Check the logs using the commands mentioned above
2. Verify your configuration against the deployment guide
3. Search the repository issues for similar problems
4. Create a new issue with detailed information about your problem, including:
   - Steps to reproduce
   - Expected vs actual behavior
   - Relevant logs
   - Your environment (OS, Docker version, etc.)