# 📅 AI-Powered Personal Booking Agent using LangGraph

An intelligent **AI scheduling assistant** built with **LangGraph** that helps users manage meetings, appointments, and bookings through natural language conversations. The agent understands user intent, maintains conversational context, detects scheduling conflicts, and automatically generates booking confirmations using an agent-based workflow.

Designed using a modular multi-agent architecture, the system combines Large Language Models (LLMs), tool calling, and workflow orchestration to deliver an intuitive and context-aware scheduling experience.

---

# ✨ Features

* 🤖 Natural language scheduling assistant
* 💬 Context-aware multi-turn conversations
* 📅 Calendar availability checking
* 🔄 Intelligent conflict detection and resolution
* 💡 Automatic alternative time slot suggestions
* 🛠️ Tool calling for calendar operations
* 📊 LangGraph-based workflow orchestration
* ✅ Booking confirmation with structured summaries

---

# 🏗️ System Architecture

The application follows an **agentic workflow** where the LLM coordinates multiple tools to complete scheduling tasks.

## Workflow

```text id="dljlmc"
User
   │
   ▼
Natural Language Query
   │
   ▼
LLM Agent
   │
   ▼
LangGraph Workflow
   │
   ├──────────────┐
   ▼              ▼
Intent        Conversation
Detection        Memory
   │              │
   └──────┬───────┘
          ▼
     Tool Calling
          │
          ▼
 Calendar API / Mock Calendar
          │
          ▼
 Conflict Detection
          │
          ▼
 Alternative Suggestions
          │
          ▼
 Booking Confirmation
```

---

# ⚙️ Agent Workflow

### 🧠 Intent Understanding

Identifies the user's scheduling request and extracts relevant information such as participants, date, time, and meeting duration.

### 💬 Conversation Management

Maintains conversational context across multiple interactions, allowing users to refine or modify bookings naturally.

### 📅 Calendar Integration

Checks availability using either the Google Calendar API or mock calendar data.

### 🔄 Conflict Resolution

Detects overlapping appointments and intelligently recommends the best available alternative time slots.

### ✅ Booking Confirmation

Generates a structured booking summary after successfully scheduling the meeting.

---

# 🛠️ Tech Stack

| Category                   | Technologies                        |
| -------------------------- | ----------------------------------- |
| **Programming Language**   | Python                              |
| **LLM Framework**          | LangChain, LangGraph                |
| **Language Models**        | OpenAI / Open-Source LLMs           |
| **Backend**                | FastAPI                             |
| **Frontend**               | Streamlit                           |
| **Calendar Integration**   | Google Calendar API / Mock Database |
| **Workflow Orchestration** | LangGraph                           |
| **Tool Calling**           | LangChain Tools                     |

---

# 🚀 Getting Started

## Clone the Repository

```bash id="zjql91"
git clone <repository-url>
cd <repository-folder>
```

## Install Dependencies

```bash id="ecgscb"
pip install -r requirements.txt
```

## Configure Environment

Create a `.env` file and add the required API keys.

```env id="cgsvjp"
OPENAI_API_KEY=your_api_key
GOOGLE_CALENDAR_API_KEY=your_calendar_key
```

## Run the Application

```bash id="cg3ksp"
streamlit run app.py
```

or

```bash id="w6kuxc"
uvicorn main:app --reload
```

---

# 📋 Example Capabilities

The AI agent can assist with tasks such as:

* Schedule a meeting for tomorrow at 3 PM
* Reschedule my appointment to Friday morning
* Cancel my meeting with John
* Find a free slot next week
* Book a one-hour discussion with the design team
* Suggest another time if my calendar is busy

---

# 🎯 Future Enhancements

* Google Calendar synchronization
* Microsoft Outlook integration
* Email invitation generation
* Voice-based scheduling assistant
* Multi-user scheduling
* Time zone awareness
* AI-generated meeting agendas
* Slack and Microsoft Teams integration

---

# 🏆 Achievement

🏅 **Top 7 Finalist – Praxis Hackathon**

This project was developed during the **Praxis Hackathon**, where it was recognized among the **Top 7 teams** for its intelligent use of AI agents, LangGraph workflows, and conversational scheduling automation.

### Certificate

<p align="center">
  <img src="https://github.com/user-attachments/assets/5d514d6f-96c5-4267-9e73-56a0b7095af5" alt="Praxis Hackathon Certificate"/>
</p>
