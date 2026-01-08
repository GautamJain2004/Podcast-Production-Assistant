"""
Streamlit Frontend for AI Podcast Production Suite

A user-friendly web interface for generating podcast content with AI.
Enhanced with real-time progress tracking and comprehensive citation display.
"""

import streamlit as st
import sys
import os
from pathlib import Path
import json
from datetime import datetime
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import PodcastProductionApp
from schemas.state_models import PodcastProductionState
from tools.dialogue_simulator import DialogueSimulator
from config.settings import get_gemini_client

# Configure logging for frontend
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page configuration
st.set_page_config(
    page_title="AI Podcast Production Suite",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        margin-bottom: 2rem;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .stButton>button {
        width: 100%;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        color: white;
        font-weight: bold;
        padding: 0.75rem;
        border-radius: 10px;
        border: none;
    }
    .stButton>button:hover {
        background: linear-gradient(90deg, #764ba2 0%, #667eea 100%);
    }
    .success-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .info-box {
        padding: 1rem;
        border-radius: 10px;
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
    .stat-card {
        padding: 1.5rem;
        border-radius: 10px;
        background: white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        text-align: center;
    }
    .stat-number {
        font-size: 2rem;
        font-weight: bold;
        color: #667eea;
    }
    .stat-label {
        font-size: 0.9rem;
        color: #666;
        margin-top: 0.5rem;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'generated' not in st.session_state:
    st.session_state.generated = False
if 'final_state' not in st.session_state:
    st.session_state.final_state = None
if 'output_dir' not in st.session_state:
    st.session_state.output_dir = None
if 'generation_error' not in st.session_state:
    st.session_state.generation_error = None
if 'generation_time' not in st.session_state:
    st.session_state.generation_time = 0
if 'dialogue_data' not in st.session_state:
    st.session_state.dialogue_data = None

# Header
st.markdown('<h1 class="main-header">🎙️ AI Podcast Production Suite</h1>', unsafe_allow_html=True)
st.markdown('<p style="text-align: center; color: #666; font-size: 1.1rem;">Transform any topic into a complete podcast package with AI</p>', unsafe_allow_html=True)

# Sidebar
with st.sidebar:
    st.image("https://img.icons8.com/fluency/96/000000/podcast.png", width=80)
    st.title("Settings")
    
    # Topic input - use session state for persistence
    if 'topic_value' not in st.session_state:
        st.session_state.topic_value = ''
    
    topic = st.text_input(
        "📝 Podcast Topic",
        value=st.session_state.topic_value,
        placeholder="e.g., AI in Healthcare, Quantum Computing...",
        help="Enter the main topic for your podcast episode",
        autocomplete="off",
        key="topic_input"
    )
    
    # Update session state when topic changes
    if topic != st.session_state.topic_value:
        st.session_state.topic_value = topic
    
    # Tone selection
    tone = st.selectbox(
        "🎭 Content Tone",
        ["conversational", "formal", "humorous", "technical", "storytelling"],
        help="Choose the tone/style for your podcast content"
    )
    
    # Research mode
    research_mode = st.radio(
        "🔍 Research Mode",
        ["Enhanced (Recommended)", "Basic"],
        help="Enhanced: Web + YouTube + Academic papers (faster with parallel execution)\nBasic: Web search only"
    )
    use_enhanced = research_mode == "Enhanced (Recommended)"
    
    # Log level
    log_level = st.selectbox(
        "📊 Log Level",
        ["INFO", "DEBUG", "WARNING", "ERROR"],
        help="Set the logging verbosity"
    )
    
    st.divider()
    
    # Features info
    st.markdown("### ✨ Features")
    if use_enhanced:
        st.success("✅ Web Search (Serper)")
        st.success("✅ YouTube Transcripts")
        st.success("✅ Academic Papers (arXiv, PubMed)")
        st.success("✅ Parallel Execution")
        st.success("✅ Smart Citation System")
        st.success("✅ Fact Checking")
    else:
        st.success("✅ Web Search (Serper)")
        st.info("⚪ YouTube (disabled)")
        st.info("⚪ Academic (disabled)")
        st.info("⚪ Parallel (disabled)")
        st.success("✅ Smart Citation System")
        st.success("✅ Fact Checking")
    
    st.divider()
    
    # About
    with st.expander("ℹ️ About"):
        st.markdown("""
        **AI Podcast Production Suite v2.3**
        
        **Powered by:**
        - 🤖 Google Gemini 2.5 Flash
        - 🔧 Google ADK (Agent Development Kit)
        - 🕸️ LangGraph (Workflow Engine)
        - 🔍 Serper API (Web Search)
        - 📺 YouTube Transcript API
        - 📚 arXiv & PubMed APIs
        
        **Features:**
        - ✅ Multi-source parallel research
        - ✅ Smart citation management
        - ✅ Automated fact-checking
        - ✅ Professional script writing
        - ✅ Social media content generation
        - ✅ Quality assurance review
        
        **Architecture:**
        - Agent Registry System
        - A2A (Agent-to-Agent) Communication
        - Pydantic State Management
        - Streamlit Web Interface
        """)

# Main content area
if not st.session_state.generated:
    # Input section
    st.markdown("## 🚀 Generate Your Podcast")
    
    if st.button("🎬 Generate Podcast", disabled=not topic):
        if not topic:
            # Use container to limit width of error box
            error_col1, error_col2, error_col3 = st.columns([1, 2, 1])
            with error_col2:
                st.error("⚠️ Please enter a topic first!")
        else:
                # Show progress
                start_time = datetime.now()
                with st.spinner("🔄 Generating your podcast..."):
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    try:
                        # Initialize app
                        status_text.text("🔧 Initializing AI agents (ADK + LangGraph)...")
                        progress_bar.progress(5)
                        
                        app = PodcastProductionApp(
                            log_level=log_level,
                            use_enhanced_research=use_enhanced,
                            retry_mode="persistent"  # Use persistent retry mode - keeps trying until success
                        )
                        
                        # Create initial state
                        status_text.text("📝 Processing topic...")
                        progress_bar.progress(10)
                        
                        state = app.create_initial_state(topic, tone)
                        
                        # Execute workflow
                        status_text.text("🎯 Starting workflow...")
                        progress_bar.progress(15)
                        
                        app.callback.on_workflow_start(state)
                        
                        # Execute agents with detailed progress
                        stages = [
                            (20, "� Refining  topic with AI..."),
                            (30, "� Gaethering research (web, YouTube, academic)..." if use_enhanced else "📚 Gathering web research..."),
                            (45, "📋 Creating structured outline..."),
                            (60, "✍️ Writing podcast script..."),
                            (70, "✅ Fact-checking claims..."),
                            (80, "� Grenerating show notes..."),
                            (85, "📱 Creating social media posts..."),
                            (90, "🎯 Final quality review..."),
                            (95, "💾 Saving all outputs...")
                        ]
                        
                        for progress, message in stages:
                            status_text.text(message)
                            progress_bar.progress(progress)
                            
                            # Add small delay for visual feedback
                            import time
                            time.sleep(0.3)
                        
                        final_state = app.execute_workflow_inprocess(state)
                        
                        # Generate outputs
                        status_text.text("💾 Writing files to disk...")
                        progress_bar.progress(98)
                        
                        output_dir = app.generate_outputs_from_state(final_state)
                        
                        app.callback.on_workflow_end(final_state)
                        
                        # Complete
                        progress_bar.progress(100)
                        status_text.text("✅ Complete!")
                        
                        # Calculate generation time
                        generation_time = (datetime.now() - start_time).total_seconds()
                        
                        # Store in session state
                        st.session_state.generated = True
                        st.session_state.final_state = final_state
                        st.session_state.output_dir = output_dir
                        st.session_state.generation_time = generation_time
                        st.session_state.generation_error = None
                        
                        st.rerun()
                        
                    except Exception as e:
                        st.session_state.generation_error = str(e)
                        logger.error(f"Generation failed: {e}", exc_info=True)
                        st.error(f"❌ Generation Failed: {str(e)}")
                        st.error("Please check your API keys in the .env file and try again.")
                        with st.expander("🔍 Error Details"):
                            st.exception(e)
    
    if not topic:
        # Use container to limit width of info box
        info_col1, info_col2, info_col3 = st.columns([1, 2, 1])
        with info_col2:
            st.info("👆 Enter a topic in the sidebar to get started!")
        
        # Show example topics
        st.markdown("### 💡 Example Topics")
        examples = [
            "🤖 AI in Healthcare: Diagnosis and Treatment",
            "🌍 Climate Change Solutions for 2025",
            "🎮 The Rise of Esports in India",
            "🧠 Mental Health in the Digital Age",
            "🚀 Space Exploration: Mars Missions",
            "💰 Cryptocurrency and Blockchain Technology",
            "🎵 The Evolution of Music Streaming",
            "🏃 Fitness Trends and Wellness"
        ]
        
        cols = st.columns([1, 1], gap="small")
        for i, example in enumerate(examples):
            with cols[i % 2]:
                if st.button(example, key=f"example_{i}"):
                    # Extract topic from example
                    extracted_topic = example.split(": ", 1)[-1] if ": " in example else example.split(" ", 1)[-1]
                    # Update session state
                    st.session_state.topic_value = extracted_topic
                    st.rerun()
        
    # Display any previous errors
    if st.session_state.generation_error:
        st.error(f"⚠️ Previous generation failed: {st.session_state.generation_error}")
        if st.button("Clear Error"):
            st.session_state.generation_error = None
            st.rerun()

else:
    # Results section
    state = st.session_state.final_state
    output_dir = st.session_state.output_dir
    
    # Success message
    st.markdown('<div class="success-box">', unsafe_allow_html=True)
    st.markdown("### ✅ Podcast Generated Successfully!")
    st.markdown(f"**Topic:** {state.selected_refined_topic or state.initial_topic}")
    st.markdown(f"**Tone:** {state.tone.title()}")
    if st.session_state.generation_time:
        st.markdown(f"**Generation Time:** {st.session_state.generation_time:.1f} seconds")
    st.markdown('</div>', unsafe_allow_html=True)
    
    # Statistics
    st.markdown("## 📊 Content Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-number">{len(state.research_materials)}</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label">Research Sources</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col2:
        word_count = len(state.final_script.split()) if state.final_script else 0
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-number">{word_count:,}</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label">Script Words</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col3:
        duration = state.estimated_duration_min or 0
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-number">{duration:.1f}</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label">Minutes</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    with col4:
        social_count = sum(len(posts) for posts in state.social_posts.values()) if state.social_posts else 0
        st.markdown('<div class="stat-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="stat-number">{social_count}</div>', unsafe_allow_html=True)
        st.markdown('<div class="stat-label">Social Posts</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
    # Tabs for content
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["Script", "Dialogue", "Summary", "Social Media", "Citations", "Research"])
    
    with tab1:
        st.markdown("### Podcast Script")
        if state.final_script:
            st.markdown(state.final_script)
            st.download_button(
                "⬇️ Download Script",
                state.final_script,
                file_name=f"script_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
        else:
            st.warning("No script generated")
    
    with tab2:
        st.markdown("### 💬 Dialogue Simulation")
        st.info("🎭 Convert your script into a host-guest conversation for practice or polishing!")
        
        if state.final_script:
            # Dialogue simulation controls
            col1, col2 = st.columns(2)
            
            with col1:
                num_speakers = st.selectbox(
                    "Number of Speakers",
                    [2, 3, 4],
                    help="Choose how many people will be in the conversation"
                )
            
            with col2:
                conversation_style = st.selectbox(
                    "Conversation Style",
                    ["conversational", "formal", "casual", "debate"],
                    format_func=lambda x: {
                        "conversational": "💬 Conversational (Natural & Friendly)",
                        "formal": "🎩 Formal (Professional & Structured)",
                        "casual": "😊 Casual (Relaxed & Fun)",
                        "debate": "⚔️ Debate (Multiple Perspectives)"
                    }.get(x, x.title())
                )
            
            # Custom speaker names
            with st.expander("🎤 Customize Speaker Names (Optional)"):
                speaker_names = []
                cols = st.columns(num_speakers)
                
                default_names = {
                    2: ["Host", "Guest"],
                    3: ["Host", "Guest 1", "Guest 2"],
                    4: ["Host", "Co-host", "Guest 1", "Guest 2"]
                }
                
                for i, col in enumerate(cols):
                    with col:
                        name = st.text_input(
                            f"Speaker {i+1}",
                            value=default_names[num_speakers][i],
                            key=f"speaker_{i}"
                        )
                        speaker_names.append(name)
            
            # Generate dialogue button
            if st.button("🎬 Generate Dialogue", key="generate_dialogue"):
                with st.spinner("🎭 Creating dialogue simulation..."):
                    try:
                        # Initialize dialogue simulator
                        gemini_client = get_gemini_client()
                        simulator = DialogueSimulator(gemini_client)
                        
                        # Generate dialogue
                        dialogue_data = simulator.simulate_dialogue(
                            script=state.final_script,
                            num_speakers=num_speakers,
                            speaker_names=speaker_names if speaker_names else None,
                            conversation_style=conversation_style
                        )
                        
                        if dialogue_data.get("success"):
                            # Store in session state
                            st.session_state.dialogue_data = dialogue_data
                            st.success("✅ Dialogue generated successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ Failed to generate dialogue: {dialogue_data.get('error')}")
                    
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        logger.error(f"Dialogue generation failed: {e}", exc_info=True)
            
            # Display generated dialogue
            if 'dialogue_data' in st.session_state and st.session_state.dialogue_data and st.session_state.dialogue_data.get("success"):
                dialogue_data = st.session_state.dialogue_data
                
                st.divider()
                
                # Dialogue info
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Speakers", dialogue_data.get("num_speakers", 0))
                with col2:
                    st.metric("Total Lines", dialogue_data.get("total_lines", 0))
                with col3:
                    st.metric("Style", dialogue_data.get("style", "").title())
                
                st.markdown("#### 🎭 Dialogue Script")
                
                # Display dialogue with speaker colors
                dialogue_lines = dialogue_data.get("dialogue_lines", [])
                
                # Color scheme for speakers
                speaker_colors = {
                    0: "#667eea",  # Purple
                    1: "#f093fb",  # Pink
                    2: "#4facfe",  # Blue
                    3: "#43e97b"   # Green
                }
                
                for i, line in enumerate(dialogue_lines):
                    speaker = line.get("speaker", "Unknown")
                    text = line.get("text", "")
                    
                    # Get speaker index for color
                    speaker_idx = dialogue_data.get("speaker_names", []).index(speaker) if speaker in dialogue_data.get("speaker_names", []) else 0
                    color = speaker_colors.get(speaker_idx, "#666")
                    
                    # Display with colored speaker name
                    st.markdown(
                        f"<div style='margin: 1rem 0; padding: 0.75rem; background: {color}10; border-left: 4px solid {color}; border-radius: 4px;'>"
                        f"<strong style='color: {color};'>{speaker}:</strong> {text}"
                        f"</div>",
                        unsafe_allow_html=True
                    )
                
                st.divider()
                
                # Export options
                st.markdown("#### 📥 Export Dialogue")
                
                # Create simulator instance for export
                gemini_client = get_gemini_client()
                simulator = DialogueSimulator(gemini_client)
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    # Markdown format
                    markdown_dialogue = simulator.format_dialogue_for_display(dialogue_data)
                    st.download_button(
                        "📝 Download Markdown",
                        markdown_dialogue,
                        file_name=f"dialogue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                        mime="text/markdown"
                    )
                
                with col2:
                    # Plain text format
                    plain_dialogue = simulator.export_dialogue_script(dialogue_data, format="plain")
                    st.download_button(
                        "📄 Download Plain Text",
                        plain_dialogue,
                        file_name=f"dialogue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                
                with col3:
                    # Screenplay format
                    screenplay_dialogue = simulator.export_dialogue_script(dialogue_data, format="screenplay")
                    st.download_button(
                        "🎬 Download Screenplay",
                        screenplay_dialogue,
                        file_name=f"dialogue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain"
                    )
                
                # Clear dialogue button
                if st.button("🔄 Generate New Dialogue"):
                    del st.session_state.dialogue_data
                    st.rerun()
            
            elif 'dialogue_data' not in st.session_state:
                st.info("👆 Click 'Generate Dialogue' to create a host-guest conversation from your script")
        
        else:
            st.warning("No script available. Generate a podcast first!")
    
    with tab3:
        st.markdown("### Episode Summary")
        if state.show_notes:
            st.markdown(state.show_notes)
            st.download_button(
                "⬇️ Download Summary",
                state.show_notes,
                file_name=f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown"
            )
        else:
            st.warning("No summary generated")
    
    with tab4:
        st.markdown("### Social Media Posts")
        if state.social_posts:
            for platform, posts in state.social_posts.items():
                if posts:
                    st.markdown(f"#### {platform.title()}")
                    for i, post in enumerate(posts, 1):
                        st.info(f"**Post {i}:** {post}")
        else:
            st.warning("No social media posts generated")
    
    with tab5:
        st.markdown("### Citations & References")
        
        if state.citations_data:
            citations_data = state.citations_data
            
            # Summary metrics
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Total Citations", citations_data.get('total_citations', 0))
            with col2:
                used = citations_data.get('used_citations', 0)
                total = citations_data.get('total_citations', 1)
                usage_pct = (used / total * 100) if total > 0 else 0
                st.metric("Used Citations", f"{used} ({usage_pct:.0f}%)")
            with col3:
                # Count unique sources
                citations_list = citations_data.get('citations', [])
                unique_sources = len(set(c.get('url', '') for c in citations_list if c.get('url')))
                st.metric("Unique Sources", unique_sources)
            
            # By type with visual breakdown
            st.markdown("#### 📊 Sources by Type")
            by_type = citations_data.get('by_type', {})
            if by_type:
                # Create columns for each type
                type_cols = st.columns(len(by_type))
                for i, (source_type, count) in enumerate(by_type.items()):
                    with type_cols[i]:
                        type_info = {
                            "web": ("🌐", "Web Articles", "#4285F4"),
                            "youtube": ("📺", "YouTube", "#FF0000"),
                            "arxiv": ("📄", "arXiv Papers", "#B31B1B"),
                            "pubmed": ("🏥", "PubMed", "#326295")
                        }
                        icon, name, color = type_info.get(source_type, ("📌", source_type.title(), "#666"))
                        st.markdown(f"<div style='text-align: center; padding: 1rem; background: {color}15; border-radius: 8px;'>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 2rem;'>{icon}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 1.5rem; font-weight: bold; color: {color};'>{count}</div>", unsafe_allow_html=True)
                        st.markdown(f"<div style='font-size: 0.9rem; color: #666;'>{name}</div>", unsafe_allow_html=True)
                        st.markdown("</div>", unsafe_allow_html=True)
            
            st.divider()
            
            # Filter options
            col1, col2 = st.columns([2, 1])
            with col1:
                filter_type = st.selectbox(
                    "Filter by source type:",
                    ["All"] + list(by_type.keys()),
                    format_func=lambda x: {
                        "All": "🔍 All Sources",
                        "web": "🌐 Web Articles",
                        "youtube": "📺 YouTube Videos",
                        "arxiv": "📄 arXiv Papers",
                        "pubmed": "🏥 PubMed Articles"
                    }.get(x, x.title())
                )
            with col2:
                show_unused = st.checkbox("Show unused citations", value=False)
            
            # Citations list with filtering
            st.markdown("#### 📚 Full Bibliography")
            citations = citations_data.get('citations', [])
            
            # Apply filters
            filtered_citations = []
            for citation in citations:
                # Filter by usage
                if not show_unused and citation.get('quote_count', 0) == 0:
                    continue
                # Filter by type
                if filter_type != "All" and citation.get('source_type', 'web') != filter_type:
                    continue
                filtered_citations.append(citation)
            
            if not filtered_citations:
                st.info("No citations match the selected filters.")
            else:
                st.markdown(f"*Showing {len(filtered_citations)} of {len(citations)} citations*")
                
                for citation in filtered_citations:
                    quote_count = citation.get('quote_count', 0)
                    source_type = citation.get('source_type', 'web')
                    
                    # Icon based on source type
                    type_icon = {
                        "web": "🌐",
                        "youtube": "📺",
                        "arxiv": "📄",
                        "pubmed": "🏥"
                    }.get(source_type, "📌")
                    
                    # Badge for usage
                    usage_badge = f"✅ Used {quote_count}x" if quote_count > 0 else "⚪ Unused"
                    
                    with st.expander(f"{type_icon} [{citation['source_id']}] {citation['title'][:70]}... | {usage_badge}"):
                        # Citation details
                        st.markdown(f"**Title:** {citation['title']}")
                        
                        # APA citation
                        apa = citation.get('citations', {}).get('apa', 'N/A')
                        st.markdown(f"**APA Citation:**")
                        st.code(apa, language=None)
                        
                        # URL
                        url = citation.get('url', '')
                        if url:
                            st.markdown(f"**URL:** [{url}]({url})")
                        
                        # Authors
                        authors = citation.get('authors', [])
                        if authors:
                            st.markdown(f"**Authors:** {', '.join(authors)}")
                        
                        # Publication date
                        pub_date = citation.get('publication_date', '')
                        if pub_date:
                            st.markdown(f"**Published:** {pub_date}")
                        
                        # Usage info
                        if quote_count > 0:
                            st.success(f"✅ Referenced {quote_count} time(s) in the script")
                            used_in = citation.get('used_in_sections', [])
                            if used_in:
                                st.markdown(f"**Used in:** {', '.join(used_in)}")
                        else:
                            st.info("⚪ This source was researched but not cited in the final script")
        else:
            st.warning("No citation data available. Citations are generated when using Enhanced research mode.")
    
    with tab6:
        st.markdown("### Research Materials")
        
        if state.research_materials:
            # Research summary
            total_materials = len(state.research_materials)
            web_count = sum(1 for m in state.research_materials if m.source == "web")
            youtube_count = sum(1 for m in state.research_materials if m.source == "youtube")
            arxiv_count = sum(1 for m in state.research_materials if m.source == "arxiv")
            pubmed_count = sum(1 for m in state.research_materials if m.source == "pubmed")
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("🌐 Web", web_count)
            with col2:
                st.metric("📺 YouTube", youtube_count)
            with col3:
                st.metric("📄 arXiv", arxiv_count)
            with col4:
                st.metric("🏥 PubMed", pubmed_count)
            
            st.divider()
            
            # Filter by source
            source_filter = st.selectbox(
                "Filter by source:",
                ["All", "web", "youtube", "arxiv", "pubmed"],
                format_func=lambda x: {
                    "All": "🔍 All Sources",
                    "web": "🌐 Web Articles",
                    "youtube": "📺 YouTube Videos",
                    "arxiv": "📄 arXiv Papers",
                    "pubmed": "🏥 PubMed Articles"
                }.get(x, x.title())
            )
            
            # Display materials
            filtered_materials = [m for m in state.research_materials if source_filter == "All" or m.source == source_filter]
            
            st.markdown(f"#### Research Items ({len(filtered_materials)} of {total_materials})")
            
            for i, material in enumerate(filtered_materials, 1):
                source_icon = {
                    "web": "🌐",
                    "youtube": "📺",
                    "arxiv": "📄",
                    "pubmed": "🏥"
                }.get(material.source, "📌")
                
                with st.expander(f"{source_icon} {i}. {material.title[:80]}..."):
                    st.markdown(f"**Query:** {material.query}")
                    st.markdown(f"**Source Type:** {material.source.upper()}")
                    if material.url:
                        st.markdown(f"**URL:** [{material.url}]({material.url})")
                    st.markdown(f"**Snippet:**")
                    st.info(material.snippet)
                    if material.citation_id:
                        st.markdown(f"**Citation ID:** `{material.citation_id}`")
        else:
            st.warning("No research materials available")
        
        # Fact-checking report
        if state.fact_check_report:
            st.divider()
            st.markdown("### ✅ Fact-Checking Report")
            
            report = state.fact_check_report
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Claims Checked", report.claims_checked)
            with col2:
                st.metric("Verified Claims", report.verified_claims)
            with col3:
                st.metric("Verification Rate", f"{report.verification_rate:.1f}%")
            
            if report.details:
                st.markdown("#### Detailed Fact Checks")
                for i, item in enumerate(report.details, 1):
                    status_icon = "✅" if item.verified else "⚠️"
                    confidence_color = {
                        "high": "green",
                        "medium": "orange",
                        "low": "red"
                    }.get(item.confidence.lower(), "gray")
                    
                    with st.expander(f"{status_icon} Claim {i}: {item.claim[:60]}..."):
                        st.markdown(f"**Claim:** {item.claim}")
                        st.markdown(f"**Verified:** {'✅ Yes' if item.verified else '⚠️ No'}")
                        st.markdown(f"**Confidence:** :{confidence_color}[{item.confidence.upper()}]")
                        if item.supporting_evidence:
                            st.markdown(f"**Evidence:** {item.supporting_evidence}")
                        if item.source_urls:
                            st.markdown("**Sources:**")
                            for url in item.source_urls:
                                st.markdown(f"- [{url}]({url})")
    

    
    # Action buttons
    st.divider()
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col1:
        if st.button("🔄 Generate Another"):
            st.session_state.generated = False
            st.session_state.final_state = None
            st.session_state.output_dir = None
            st.rerun()
    
    with col2:
        if st.button("📂 Open Output Folder"):
            import subprocess
            if os.name == 'nt':  # Windows
                subprocess.Popen(f'explorer "{os.path.abspath(output_dir)}"')
            else:  # Mac/Linux
                subprocess.Popen(['open' if sys.platform == 'darwin' else 'xdg-open', output_dir])
            st.success("✅ Opening folder...")
    
    with col3:
        # Export all data as JSON
        export_data = {
            "topic": state.initial_topic,
            "refined_topic": state.selected_refined_topic,
            "tone": state.tone,
            "script": state.final_script,
            "show_notes": state.show_notes,
            "social_posts": state.social_posts,
            "sources": state.all_sources,
            "citations": state.citations_data,
            "stats": {
                "research_sources": len(state.research_materials),
                "word_count": len(state.final_script.split()) if state.final_script else 0,
                "duration_min": state.estimated_duration_min,
                "social_posts": sum(len(posts) for posts in state.social_posts.values()) if state.social_posts else 0
            }
        }
        
        st.download_button(
            "📦 Export All Data (JSON)",
            json.dumps(export_data, indent=2, default=str),
            file_name=f"podcast_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )

# Footer
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; padding: 2rem;">
    <p>🎙️ <strong>AI Podcast Production Suite v2.3</strong></p>
    <p>Powered by Google Gemini 2.5 Flash • ADK + LangGraph • Multi-Source Research • Smart Citations</p>
    <p style="font-size: 0.8rem; margin-top: 1rem;">
        Built with Streamlit • Enhanced with Parallel Processing • Professional Quality Output
    </p>
</div>
""", unsafe_allow_html=True)
