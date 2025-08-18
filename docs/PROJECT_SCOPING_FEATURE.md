# Project Scoping Analysis Feature

## Overview

The DTCE AI Bot now includes comprehensive project scoping analysis capabilities that can:

1. **Read and analyze client requests and RFPs**
2. **Find similar past projects** from the DTCE database
3. **Generate design philosophy recommendations** based on past experience
4. **Identify potential issues and solutions** from similar projects
5. **Provide compliance guidance** (PS1, building consent, etc.)

## How It Works

### Automatic Detection

The bot automatically detects project scoping requests when messages contain keywords like:
- "please review this request"
- "rfp" or "request for proposal"
- "similar past projects"
- "design philosophy"
- "marquee", "certification", "quote for ps1"

### Manual Activation

You can also explicitly trigger analysis with:
```
/analyze [your project request text]
```

### Example Usage

**Client Request:**
```
Hi Team,
I have a 15x40m double decker marquee that needs PS1 certification in Wellington. 
The marquee is rated for 120kph wind loads and will be installed on a concrete pad.
Could you provide a quote and let me know what you need from us?
```

**AI Response:**
The bot will provide:
1. **Project Overview & Classification** - Structure type, complexity assessment
2. **Similar Past Projects Analysis** - Relevant past work and lessons learned
3. **Design Philosophy & Approach** - Recommended design methodology
4. **Past Issues & Solutions** - Common problems and how they were solved
5. **Compliance & Certification Guidance** - PS1/PS3 requirements
6. **Risk Assessment & Warnings** - Potential challenges to watch for
7. **Recommendations & Next Steps** - What information is still needed
8. **Cost & Timeline Insights** - Typical expectations for similar projects

## Technical Implementation

### Services Used

- **ProjectScopingService** (`dtce_ai_bot/services/project_scoping.py`)
  - Handles the core analysis logic
  - Extracts project characteristics using AI
  - Searches for similar projects in Azure Cognitive Search
  - Generates comprehensive recommendations

- **DocumentQAService** (`dtce_ai_bot/services/document_qa.py`)
  - Enhanced with additional project analysis methods
  - Provides backup/alternative analysis approaches

### API Endpoints

- **POST /api/project-scoping/analyze** - REST API for project analysis
- **Teams Bot Integration** - Automatic handling in Microsoft Teams

### Key Features

1. **Intelligent Characteristic Extraction**
   - Project type (marquee, building, bridge, etc.)
   - Dimensions and scale
   - Location and environmental factors
   - Load requirements (wind, seismic, live loads)
   - Materials and construction methods
   - Compliance requirements

2. **Smart Project Matching**
   - Semantic search through project database
   - Similarity scoring based on multiple factors
   - Relevance ranking and filtering

3. **Experience-Based Recommendations**
   - Analysis of past project outcomes
   - Common issues and proven solutions
   - Risk assessment based on historical data
   - Design philosophy derived from successful projects

## Teams Bot Integration

### Commands

- `help` - Shows updated help with project scoping info
- `analyze [request]` - Explicit project analysis
- Automatic detection of client requests

### Response Format

The bot provides structured responses with:
- 📋 Project Analysis Report header
- 📊 Extracted characteristics summary
- 🔍 Similar projects found
- Detailed recommendations and guidance
- Professional client-ready language

## Example Scenarios

### Scenario 1: Marquee Certification
**Input:** Client request for 15x40m marquee PS1 certification in Wellington
**Output:** Analysis of similar marquee projects, wind load considerations, foundation recommendations, compliance pathway

### Scenario 2: Building Structure RFP
**Input:** RFP for commercial building structural design
**Output:** Relevant past building projects, design approach recommendations, timeline expectations, risk factors

### Scenario 3: Infrastructure Project
**Input:** Bridge or infrastructure scoping document
**Output:** Similar infrastructure experience, regulatory requirements, technical challenges, cost factors

## Benefits

1. **Faster Response to Client Inquiries** - Instant analysis instead of manual research
2. **Consistent Quality** - Standardized approach based on best practices
3. **Risk Mitigation** - Early identification of potential issues
4. **Knowledge Leverage** - Automatic access to organizational experience
5. **Professional Presentation** - Client-ready responses with proper formatting

## Future Enhancements

- Integration with document upload for RFP file analysis
- Cost estimation based on similar project data
- Timeline prediction using historical project durations
- Resource allocation recommendations
- Automated proposal generation

## Usage Tips

- Include as much detail as possible in project requests
- Mention specific requirements like dimensions, loads, location
- Reference any standards or compliance needs
- Ask follow-up questions to get more specific guidance

## Technical Notes

- Uses Azure OpenAI GPT-4 for intelligent analysis
- Integrates with Azure Cognitive Search for project database queries
- Supports both text-based and file-based analysis
- Provides structured JSON responses for API integration
- Teams bot automatically formats responses for readability
