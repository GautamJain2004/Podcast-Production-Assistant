"""
Dialogue Simulator Tool

Converts podcast scripts into host-guest conversation format for practice or polishing.
"""

import logging
from typing import List, Dict, Any, Optional
from google.genai import Client
from config.settings import get_gemini_model

logger = logging.getLogger(__name__)


class DialogueSimulator:
    """
    Simulates host-guest dialogue from podcast scripts.
    
    Features:
    - Converts monologue scripts to dialogue format
    - Assigns speaker roles (Host, Guest, Co-host)
    - Adds natural conversation flow
    - Includes reactions and interjections
    """
    
    def __init__(self, gemini_client: Client):
        self.gemini_client = gemini_client
        self.logger = logging.getLogger(__name__)
    
    def simulate_dialogue(
        self,
        script: str,
        num_speakers: int = 2,
        speaker_names: Optional[List[str]] = None,
        conversation_style: str = "conversational"
    ) -> Dict[str, Any]:
        """
        Convert a script into a host-guest dialogue.
        
        Args:
            script: The original podcast script
            num_speakers: Number of speakers (2-4)
            speaker_names: Optional custom speaker names
            conversation_style: Style of conversation (conversational, formal, casual, debate)
        
        Returns:
            Dictionary with dialogue data
        """
        self.logger.info(f"Simulating dialogue with {num_speakers} speakers")
        
        # Default speaker names
        if not speaker_names:
            if num_speakers == 2:
                speaker_names = ["Host", "Guest"]
            elif num_speakers == 3:
                speaker_names = ["Host", "Guest 1", "Guest 2"]
            else:
                speaker_names = ["Host", "Co-host", "Guest 1", "Guest 2"]
        
        # Create prompt for dialogue generation
        prompt = self._create_dialogue_prompt(script, num_speakers, speaker_names, conversation_style)
        
        try:
            response = self.gemini_client.models.generate_content(
                model=get_gemini_model(),
                contents=prompt
            )
            
            dialogue_text = response.text
            
            # Parse dialogue into structured format
            dialogue_lines = self._parse_dialogue(dialogue_text, speaker_names)
            
            return {
                "success": True,
                "dialogue_text": dialogue_text,
                "dialogue_lines": dialogue_lines,
                "num_speakers": num_speakers,
                "speaker_names": speaker_names,
                "style": conversation_style,
                "total_lines": len(dialogue_lines)
            }
            
        except Exception as e:
            self.logger.error(f"Dialogue simulation failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "dialogue_text": "",
                "dialogue_lines": []
            }
    
    def _create_dialogue_prompt(
        self,
        script: str,
        num_speakers: int,
        speaker_names: List[str],
        style: str
    ) -> str:
        """Create the prompt for dialogue generation."""
        
        style_instructions = {
            "conversational": "Create a natural, friendly conversation with occasional humor and personal anecdotes.",
            "formal": "Create a professional, structured discussion with clear transitions and formal language.",
            "casual": "Create a relaxed, informal chat with casual language, jokes, and tangents.",
            "debate": "Create an engaging debate format with different perspectives and counterarguments."
        }
        
        instruction = style_instructions.get(style, style_instructions["conversational"])
        
        prompt = f"""
Convert the following podcast script into a dynamic {style} dialogue between {num_speakers} speakers.

Speakers: {', '.join(speaker_names)}

Instructions:
1. {instruction}
2. Break down the content into natural back-and-forth exchanges
3. Add reactions, questions, and interjections to make it feel authentic
4. Include transitions like "That's interesting...", "Wait, so...", "I see what you mean..."
5. Distribute the content naturally among all speakers
6. Keep the core information and key points from the original script
7. Add personality to each speaker (Host is engaging, Guest is knowledgeable, etc.)
8. Format as: **Speaker Name:** Dialogue text

Original Script:
{script}

Generate the dialogue:
"""
        return prompt
    
    def _parse_dialogue(self, dialogue_text: str, speaker_names: List[str]) -> List[Dict[str, str]]:
        """
        Parse dialogue text into structured format.
        
        Returns:
            List of dialogue lines with speaker and text
        """
        lines = []
        current_speaker = None
        current_text = []
        
        for line in dialogue_text.split('\n'):
            line = line.strip()
            if not line:
                continue
            
            # Check if line starts with a speaker name
            is_speaker_line = False
            for speaker in speaker_names:
                # Match patterns like "**Host:**" or "Host:" or "HOST:"
                patterns = [
                    f"**{speaker}:**",
                    f"**{speaker.upper()}:**",
                    f"{speaker}:",
                    f"{speaker.upper()}:"
                ]
                
                for pattern in patterns:
                    if line.startswith(pattern):
                        # Save previous speaker's text
                        if current_speaker and current_text:
                            lines.append({
                                "speaker": current_speaker,
                                "text": ' '.join(current_text).strip()
                            })
                        
                        # Start new speaker
                        current_speaker = speaker
                        current_text = [line.replace(pattern, '').strip()]
                        is_speaker_line = True
                        break
                
                if is_speaker_line:
                    break
            
            # If not a speaker line, add to current speaker's text
            if not is_speaker_line and current_speaker:
                current_text.append(line)
        
        # Add the last speaker's text
        if current_speaker and current_text:
            lines.append({
                "speaker": current_speaker,
                "text": ' '.join(current_text).strip()
            })
        
        return lines
    
    def format_dialogue_for_display(self, dialogue_data: Dict[str, Any]) -> str:
        """
        Format dialogue data for display.
        
        Args:
            dialogue_data: Output from simulate_dialogue()
        
        Returns:
            Formatted dialogue string
        """
        if not dialogue_data.get("success"):
            return f"Error: {dialogue_data.get('error', 'Unknown error')}"
        
        lines = dialogue_data.get("dialogue_lines", [])
        if not lines:
            return dialogue_data.get("dialogue_text", "")
        
        formatted = []
        formatted.append(f"# Podcast Dialogue Simulation")
        formatted.append(f"**Style:** {dialogue_data.get('style', 'conversational').title()}")
        formatted.append(f"**Speakers:** {', '.join(dialogue_data.get('speaker_names', []))}")
        formatted.append(f"**Total Lines:** {len(lines)}")
        formatted.append("\n---\n")
        
        for line in lines:
            speaker = line.get("speaker", "Unknown")
            text = line.get("text", "")
            formatted.append(f"**{speaker}:** {text}\n")
        
        return '\n'.join(formatted)
    
    def export_dialogue_script(self, dialogue_data: Dict[str, Any], format: str = "markdown") -> str:
        """
        Export dialogue in various formats.
        
        Args:
            dialogue_data: Output from simulate_dialogue()
            format: Export format (markdown, plain, screenplay)
        
        Returns:
            Formatted dialogue string
        """
        if format == "markdown":
            return self.format_dialogue_for_display(dialogue_data)
        
        elif format == "plain":
            lines = dialogue_data.get("dialogue_lines", [])
            return '\n\n'.join([f"{line['speaker']}: {line['text']}" for line in lines])
        
        elif format == "screenplay":
            lines = dialogue_data.get("dialogue_lines", [])
            formatted = ["PODCAST EPISODE - DIALOGUE SCRIPT", "=" * 50, ""]
            
            for line in lines:
                formatted.append(f"{line['speaker'].upper()}")
                formatted.append(f"    {line['text']}")
                formatted.append("")
            
            return '\n'.join(formatted)
        
        else:
            return dialogue_data.get("dialogue_text", "")
