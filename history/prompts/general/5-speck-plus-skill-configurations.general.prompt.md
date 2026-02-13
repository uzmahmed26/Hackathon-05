---
id: 5
title: Speck Plus Skill Configurations
stage: general
date: 2026-02-11
surface: agent
model: Qwen
feature: customer-success-ai
branch: 1-customer-success-ai
user: user
command: manual-skill-config-implementation
labels: [speck-plus, skills, configuration]
links:
  spec: ../specs/1-customer-success-ai/spec.md
  ticket: null
  adr: null
  pr: null
files:
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\agent\\skills\\knowledge_retrieval.yaml
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\agent\\skills\\sentiment_analysis.yaml
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\agent\\skills\\escalation_decision.yaml
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\agent\\skills\\channel_adaptation.yaml
 - C:\\Users\\laptop world\\Desktop\\Hack-05\\customer-success-fte\\agent\\skills\\customer_identification.yaml
tests:
 - null
---

## Prompt

Create the 5 Speck Plus skill configurations.

Create these files in agent/skills/:

FILE 1: knowledge_retrieval.yaml
```yaml
skill:
  name: knowledge_retrieval
  description: Search product documentation semantically for relevant answers
  model: qwen2.5-72b-instruct
  temperature: 0.3
  max_tokens: 500
  
  input_schema:
    query:
      type: string
      description: Customer's question to search for
      required: true
    max_results:
      type: integer
      description: Maximum number of results to return
      default: 5
      
  output_schema:
    results:
      type: array
      items:
        type: object
        properties:
          title: string
          content: string
          relevance: float
    confidence:
      type: float
      description: Overall confidence in search results
      
  system_prompt: |
    You are a knowledge base search specialist.
    Given a customer query, find the most relevant documentation.
    Return results with relevance scores (0-1).
    
  examples:
    - input:
        query: "How do I reset my password?"
        max_results: 3
      output:
        results:
          - title: "Password Reset Guide"
            content: "To reset your password, click 'Forgot Password' on the login page..."
            relevance: 0.95
        confidence: 0.9
```

FILE 2: sentiment_analysis.yaml
```yaml
skill:
  name: sentiment_analysis
  description: Analyze customer sentiment and emotional state
  model: qwen2.5-72b-instruct
  temperature: 0.1
  max_tokens: 100
  
  input_schema:
    message:
      type: string
      description: Customer message to analyze
      required: true
      
  output_schema:
    sentiment:
      type: float
      description: Sentiment score from -1 (very negative) to 1 (very positive)
    emotion:
      type: string
      enum: [happy, neutral, frustrated, angry, confused, grateful]
    confidence:
      type: float
      
  system_prompt: |
    Analyze the sentiment and emotion in customer messages.
    Return a sentiment score from -1 to 1 and identify the primary emotion.
    
  examples:
    - input:
        message: "This is TERRIBLE! I'm so frustrated!"
      output:
        sentiment: -0.8
        emotion: "angry"
        confidence: 0.95
```

FILE 3: escalation_decision.yaml
FILE 4: channel_adaptation.yaml
FILE 5: customer_identification.yaml

Create all 5 YAML files with complete configurations following the same pattern.
Include system prompts and examples for each.

## Response snapshot

Successfully created all 5 Speck Plus skill configuration files in the agent/skills/ directory:

1. knowledge_retrieval.yaml - Configuration for searching product documentation with semantic search capabilities
2. sentiment_analysis.yaml - Configuration for analyzing customer sentiment and emotional state
3. escalation_decision.yaml - Configuration for determining if customer queries require human escalation
4. channel_adaptation.yaml - Configuration for adapting response tone and format for different communication channels
5. customer_identification.yaml - Configuration for identifying customer type and profile from available data

Each configuration includes:
- Skill name and description
- Model specification (qwen2.5-72b-instruct)
- Temperature and max_tokens settings
- Input and output schemas with detailed field definitions
- System prompts tailored to each skill's purpose
- Example inputs and outputs for demonstration

All configurations follow the same pattern and are ready for use with the Speck Plus framework.

## Outcome

- ✅ Impact: Complete Speck Plus skill configurations created
- 🧪 Tests: No automated tests for configuration files
- 📁 Files: 5 YAML configuration files created
- 🔁 Next prompts: Ready for Speck Plus integration
- 🧠 Reflection: Configurations are complete and consistent

## Evaluation notes (flywheel)

- Failure modes observed: None
- Graders run and results (PASS/FAIL): N/A
- Prompt variant (if applicable): N/A
- Next experiment (smallest change to try): Integrate with Speck Plus framework