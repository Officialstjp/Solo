# Solo Assistant Agent Architecture Sketch
Solo should employ a multi-agent architecture, focussed on modularizing tasks, responsibility and fast-access data contexts.
This project should explore opportunities to optimize agent <-> system interactions, by utilizing optimized request, data and command formats at the data level.
To put it short: Instead of interfaces optimized for humans, like browsers, up to command lines, we'll explore opportunities in low-level data interaction.
For this, we'll need to specifically define any area an agent will interact with and ensure absolute security in the defined scopes.
While specifics are still open, we can assume data operations at any architecture level we might move in have a chance cause great damage to system components.

## Data Forest
The Data Forest is the logical commulation of all data the agent architecture has access to. In it reside the Agents and their data contexts.
It should gather data from different sources, including simple file systems, Vector-DBs, aswell as commands (encoded in some way) for the agents to execute (which may be global, may be data context-limited) etc.. into a standardized optimized format for agent interaction (may be similar to current Vector-DBs)

Data from said sources should be able to be logically organized into [name open], which hold data from different sources.

## Data Contexts
Concept:
The idea behind a 'Data Context' is a dedicated area on a file-system, database, or already defined [name open] over which an Agent will have logical responsibility for.
This should be the main method of assigning a so to speak 'Role' to an agent. An agent will be able to read and provide information, aswell as write, modify and delete data based on requests in his assigned data context.

Agents should be able to delegate permissions in their data context to agents under their management. E.g.: a Code Manager should be able to allow a code worker he might create access to specific areas of his data context, if needed more specialized than himself (While a Code Manager might know where certain code is in the file structure, but only the dedicated code-worker knows it's actual contents)

Agents may have a standardized specific 'live context' area defined, which includes data always loaded in memory.
This would classicly include index files for the location of certain information in an agents own data context, aswell as indexes of which other agents store which information, allowing for fast lookups and quick localization of any data in the whole Data Forest.
This allows for clear seperation of concerns aswell as predictable context-management for the LLMs behind them.

### Isn't this just RAG?
Instead of a set of data the model has access and can learn from being defined, Data Contexts expand on the premise of one central knowledge-base, to smaller individual 'agent-owned' specialization books.


An example Sketch
A 'receptionist' Agent should take in User-Prompts and process them into a structured format best suited for further LLM Input (JSON?)
The receptionists data context will be latest User-Prompts.
The receptionist hands over the structured-up request to the Manager
The Manager processes the request and defines fields/areas with specific tasks. He then delegates these tasks to Field-specialized agents:
    A task may include:
    - Writing Code
    - Testing the Code
    - Repository maintenance
    - Updating Documentation

    These tasks could get delegated to following agents:
    - Writing Code - Code Manager
    - Testing the Code - Code Manager
    - Repository maintenance - Repository Manager
    - Updating Documentation - Repository Manager

    These request, depending on the effort needed can be delegated further. The Code Manager might define and delegate tasks as follows:
    - Gather Documentation - Research Worker
    - Sketch a code architecture - Architecture Worker
    - Review the architecture - Architecture Reviewer
    - Implement working POC - Code Teamleader
    - Test extensively, improve - Test Teamleader
    - Implement extended features - Code Teamleader
    - Test extensively - Test Teamleader
    - Write Architecture/Code Documentation - Doc Worker
    - Write Usage/End-User documentation - Doc Worker
    - Conclude Git Workflow (commit, merge, push) - Git Worker

    Teamleader agents may orchestrate development phases / areas and delegate them to further workers below them. A Code Teamleader may create an individual worker for implementing a certain component of an app, e.g.. A Test Teamleader may delegate one worker to writing tests, one to running tests and reporting results and one to evaluate them and create action plans.


A single or several delegated Agents must be assigned the task of tracking and updating data locations and indexes if needed and providing information on where data can be found if needed.

As you may have noticed, this can theorethically lead to an endless amount of agents being deployed, if the task is deemed complex enough. We will need to find a way to regulate this.
