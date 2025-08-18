    async def _handle_conversational_query(self, question: str, classification: Dict[str, Any]) -> Dict[str, Any]:
        """Handle conversational queries, greetings, or unclear input."""
        try:
            logger.info("Processing conversational query", question=question)
            
            question_lower = question.lower().strip()
            
            # Generate appropriate conversational responses
            if question_lower in ["hey", "hi", "hello"]:
                answer = "Hello! I'm the DTCE AI Assistant. I can help you find information from DTCE's project documents, templates, standards, and provide engineering guidance. What would you like to know?"
            elif question_lower in ["what", "what?"]:
                answer = """I'm here to help with engineering questions! You can ask me about:

• Past DTCE projects and case studies
• Design templates and calculation sheets  
• Building codes and standards (NZS, AS/NZS)
• Technical design guidance
• Project timelines and costs
• Best practices and methodologies

What specific information are you looking for?"""
            elif question_lower in ["really", "really?"]:
                answer = "Yes! I have access to DTCE's extensive project database and can help you find relevant information. Try asking about specific projects, technical topics, or engineering guidance you need."
            elif len(question.strip()) < 3:
                answer = "I need a bit more information to help you. Please ask a specific question about engineering, projects, standards, or anything else I can assist with!"
            else:
                # For other unclear queries, provide a helpful prompt
                answer = f"""I'm not quite sure what you're asking about with '{question}'. I'm designed to help with engineering questions and DTCE project information. 

Try asking something like:
• 'Find projects similar to a 3-story office building'
• 'Show me NZS 3101 concrete design information'
• 'What's our standard approach for steel connections?'
• 'How long does PS1 preparation typically take?'

What can I help you find?"""
            
            return {
                'answer': answer,
                'sources': [],
                'confidence': 'high',
                'documents_searched': 0,
                'search_type': 'conversational',
                'classification': classification
            }
            
        except Exception as e:
            logger.error("Conversational query failed", error=str(e))
            return {
                'answer': "Hello! I'm the DTCE AI Assistant. How can I help you with engineering questions or project information?",
                'sources': [],
                'confidence': 'medium',
                'documents_searched': 0
            }
