# DTCE AI Chatbot Demo Script

## Past Week Progress
In the past week, I focused on making the AI chatbot able to answer questions. So here it is now - it can now answer questions.

*[Show live demo with API calls]*

Let me demonstrate this...

*[Run actual API calls showing the chatbot answering questions]*

## Test Questions & Real-World Usage
These questions I only made up. I need you to give me a brief list of real questions or possible questions that engineers will ask, so that I can fine-tune the answers.

## This Week Focus
This week I will focus on:
1. **Microsoft Teams Integration** - Instead of this documentation, I will now be integrating this to the Teams chat
2. **Refining the AI chatbot answers** - Based on your real questions

## Questions & Discussion
What specific questions would you ask this system in your daily work?

---

## Demo Commands (For Reference)
```bash
# Basic project question
curl -X POST "http://localhost:8000/documents/ask?question=What%20files%20are%20in%20project%20219200" | jq '.answer'

# Content analysis
curl -X POST "http://localhost:8000/documents/ask?question=Why%20did%20the%20project%20not%20proceed" | jq '.answer'

# Email search
curl -X POST "http://localhost:8000/documents/ask?question=What%20was%20discussed%20in%20the%20DMT%20emails" | jq '.answer'
```

---

## Demo Commands (For Reference)
```bash
# Basic project question
curl -X POST "http://localhost:8000/documents/ask?question=What%20files%20are%20in%20project%20219200" | jq '.answer'

# Content analysis
curl -X POST "http://localhost:8000/documents/ask?question=Why%20did%20the%20project%20not%20proceed" | jq '.answer'

# Email search
curl -X POST "http://localhost:8000/documents/ask?question=What%20was%20discussed%20in%20the%20DMT%20emails" | jq '.answer'
```

