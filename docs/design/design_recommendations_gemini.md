# **Architectural Frameworks and Design Patterns for Robust Agentic Coding Systems on Google Cloud Platform**

The paradigm shift in autonomous agent development has transitioned from basic large language model (LLM) prompting to sophisticated agentic systems capable of reasoning, planning, and executing multi-step software engineering tasks.1 Building a production-ready agentic coding system in 2025 requires more than a simple integration of APIs; it demands a principled approach to modular architecture, strict separation of concerns, and the adoption of established design patterns to prevent the system from "inventing" ad hoc solutions that lead to technical debt and token drift.1 By leveraging Python, FastAPI, and Jinja2 within the Google Cloud Platform (GCP) ecosystem, organizations can build systems that are not only scalable and cost-effective but also secure enough to execute agent-generated code without compromising host infrastructure.3

## **Principles of Modular Architecture and Hexagonal Design**

The foundation of a robust agentic system lies in its ability to decouple the core reasoning logic from the external frameworks and delivery mechanisms. Hexagonal Architecture, or the Ports and Adapters pattern, is uniquely suited for this purpose, as it places the business rules (the domain) at the center of the application, isolating them from the complexities of HTTP protocols, database drivers, and LLM provider SDKs.6 This isolation ensures that the coding agent interacts with well-defined interfaces rather than concrete implementations, which reduces the cognitive load on the model and minimizes the tokens required for each interaction.1

### **Folder Structure and Layered Separation**

A maintainable FastAPI application begins with a folder structure that explicitly reflects these boundaries. In a 2025 best-practice setup, the application is divided into functional layers that facilitate independent testing and evolution of components.6

| Directory | Purpose | Core Components |
| :---- | :---- | :---- |
| app/api/ | Delivery Layer | Versioned routers, OAuth2 logic, HTTP filters 6 |
| app/core/ | System Configuration | Pydantic settings, security constants, global logging 6 |
| app/domain/ | Business Logic Core | Entity models, pure business rules, interface definitions 1 |
| app/services/ | Orchestration Layer | Agent reasoning loops, tool coordinators, complex workflows 8 |
| app/infrastructure/ | Implementation Adapters | Database repositories, MCP servers, cloud client wrappers 3 |
| app/prompts/ | Prompt Registry | Jinja2 templates for system and tool instructions 11 |
| app/sandbox/ | Execution Layer | Interfaces for gVisor, BentoRun, or Vertex AI Code Execution 5 |

This structure prevents the "tutorial trap" of keeping all logic in a single file, which leads to bloated prompts when an agent attempts to understand the codebase.9 By keeping modules small and focused, the system ensures that the agent only needs to "see" relevant code snippets, thereby reducing token usage and preventing context drift.8

### **Dependency Injection Beyond FastAPI**

While FastAPI includes a powerful dependency injection (DI) system through the Depends keyword, this system is primarily coupled to the HTTP request-response cycle.14 For agentic coding projects that involve long-running background tasks, scheduled jobs, or CLI-based interaction, a more robust DI framework is necessary to maintain modularity.16 Frameworks like python-dependency-injector or Wireup allow for the creation of a centralized container where dependencies are registered as providers.16

The architectural advantage of a dedicated DI container is the ability to swap implementations at runtime. For example, during local development, a repository might use a local SQLite database, whereas in production on GCP, it uses a Cloud SQL adapter.8 In the context of an agentic system, this allows the "Agent Service" to receive a "Mock LLM Client" during unit testing, ensuring that the system can be validated without incurring API costs or dealing with non-deterministic model behavior.16 This inversion of control is what makes the system resilient to changes in underlying technology.7

## **Cognitive Architectures for Autonomous Agents**

Autonomous agents are defined by their ability to use LLMs to decide the execution flow of an application with varying degrees of autonomy.20 Unlike deterministic pipelines, agentic systems use reasoning loops to determine which tools to call and how to interpret the results.13

### **The ReAct Pattern and Reasoning Loops**

The Reason and Act (ReAct) pattern is the gold standard for agentic workflows in 2025\. It structures agent behavior into explicit phases of thought, action, and observation.22 This iterative cycle allows the agent to adapt its plan based on real-time feedback from the environment, such as a failed test case or a missing library in the sandbox.13

| Phase | Description | Output Example |
| :---- | :---- | :---- |
| Thought | Reasoning about the current state and identifying gaps | "I need to check if the database connection string is set." 23 |
| Action | Selecting and executing a specific tool | get\_env\_var("DATABASE\_URL") 13 |
| Observation | Evaluating the result of the tool execution | "The environment variable is null." 13 |
| Refinement | Updating the internal plan based on the observation | "I will now check the .env file structure." 22 |

The effectiveness of the ReAct pattern depends on keeping prompts clear and minimal. Providing an agent with an unbounded set of APIs or excessive context leads to contradictions and hallucinations.13 Therefore, the architecture should implement a "Tool Registry" that dynamically provides only the tools relevant to the current task.2

### **Multi-Agent Collaboration and Task Decomposition**

As coding tasks grow in complexity, a single-agent system often struggles with "context bloat" and reduced predictability.21 The system should instead utilize multi-agent architectures where specialized agents coordinate to achieve a goal.20

The Router-Worker pattern is particularly effective for software engineering workflows. A central "Coordinator" or "Router" agent analyzes the user request and delegates sub-tasks to specialized "Worker" agents (e.g., a "Security Auditor," a "Test Architect," and a "Code Generator").2 This separation of concerns ensures that the "Code Generator" agent doesn't need to know about security audit rules, keeping its prompt focused and its token usage low.2

Another critical pattern is the Evaluator-Optimizer loop, where one agent generates a response (e.g., a Python function) and a second agent explicitly switches into "critic mode" to assess the work for accuracy, compliance, and logical consistency.20 In a coding project, the evaluator might run the generated code in a sandbox and provide the traceback to the optimizer, creating a self-healing loop that significantly improves the quality of the final output.20

## **Leveraging GCP Managed Services for Agentic Workloads**

Google Cloud Platform provides a suite of managed services that are ideal for hosting and scaling agentic coding systems while maintaining security and operational efficiency.

### **Cloud Run: The Scalable Execution Environment**

Cloud Run is the recommended platform for hosting the FastAPI delivery layer. It is a fully managed environment for running containerized applications that automatically scales up and down, including scaling to zero when idle.3 This is particularly cost-effective for agentic systems where workloads may be "spiky," characterized by intense reasoning bursts followed by long periods of inactivity.3

Cloud Run's security model is built on gVisor, which provides a two-layer sandbox consisting of a hardware-backed virtualization layer and a software kernel layer.5 This isolation allows the system to host the agent's "brain" in a secure environment that is separate from any potentially untrusted code generated by the model.5

### **Vertex AI Agent Engine and Code Execution**

For teams seeking a more integrated experience, the Vertex AI Agent Engine offers a managed runtime specifically designed for AI agents.3 It handles versioning, provides a testing playground in the GCP console, and integrates seamlessly with the Vertex AI ecosystem of models like Gemini 2.5 Flash.3

A standout feature of the Agent Engine is its managed Code Execution capability. Many agentic tasks, such as data science workflows or financial calculations, require the agent to generate and run code.5 Agent Engine Code Execution provides a secure, isolated sandbox where untrusted code can run safely, with support for file input/output up to 100MB and session state persistence for up to 14 days.12 This eliminates the need for developers to manage their own sandboxing infrastructure while ensuring that agent-generated code cannot access sensitive system resources or the internal network.5

### **Model Context Protocol (MCP) and Cloud API Registry**

The Model Context Protocol (MCP) is an emerging standard in 2025 that provides a unified way for applications to expose tools and data to LLMs.24 GCP has embraced this standard through the Cloud API Registry, which provides managed MCP servers for services like BigQuery, Cloud Storage, and Google Maps.3

| GCP Managed MCP Server | Capabilities Provided to Agents | Common Use Cases |
| :---- | :---- | :---- |
| BigQuery MCP | SQL execution, schema retrieval, ML inference | Data analysis, automated reporting 3 |
| Cloud Storage MCP | Object listing, read/write, bucket management | Data pipeline orchestration, artifact storage 26 |
| Compute Engine MCP | VM lifecycle management, status querying | Infrastructure automation, self-healing systems 30 |
| GKE MCP | Pod/node listing, health checks, scaling | Kubernetes cluster management 30 |

By using the Google Agent Development Kit (ADK), developers can connect their agents to these managed MCP tools with minimal custom code.3 This "zero custom connector" approach ensures that the coding agent uses well-established, secure interfaces to interact with cloud infrastructure, preventing the agent from "inventing" its own fragile API calls.3

## **Secure Sandboxing and Code Execution Patterns**

One of the most significant risks in an agentic coding project is the execution of code generated by a non-deterministic model.4 A single "hallucinated" command or a successful "prompt injection" attack could lead to the agent executing malicious operations, such as deleting production data or leaking API keys.4

### **The Three-Tier Defense-in-Depth Model**

A robust architecture implements a defense-in-depth strategy for code execution. This involves isolating the agent's reasoning environment from the execution environment and applying multiple layers of security.28

1. **OS-Level Isolation**: Using technologies like gVisor or micro-VMs (e.g., Firecracker or Kata Containers) to provide a hard security boundary between the host and the container.4  
2. **Resource Constraints**: Applying strict CPU, memory, and disk I/O limits at the container level to prevent runaway processes or "denial of service" attacks from buggy code.5  
3. **Network Lockdown**: Disabling outbound internet access for the sandbox unless explicitly required, and using VPC firewall rules to prevent calls to the internal application network.5

### **Implementing the BentoRun Pattern on Cloud Run**

BentoRun is an open-source example of an MCP server designed to solve the problem of secure AI-driven code execution on GCP.5 It leverages Cloud Run and gVisor to provide a "execute\_python" tool that any agent can use.5

The mechanism of BentoRun involves a precise "choreography":

* The agent's Python code is written to a temporary workspace inside the sandbox.5  
* If the agent requires GCP access, BentoRun can inject ephemeral tokens and monkey-patch standard libraries (like google.auth.default()) so the code runs with the correct user context without needing hardcoded credentials.5  
* The server monitors a special /output directory; any files generated by the code (e.g., charts, CSVs) are automatically detected and returned to the agent as binary resources.5

This pattern allows for session persistence, where an agent can write code in one step, save the result, and then perform multi-step analysis or iterative debugging in subsequent steps.5

## **Advanced Prompt Management with Jinja2**

In modular agentic systems, prompts are not mere strings but critical application components that define the "persona" and "capabilities" of each agent.11 Hardcoding prompts within the application code is a primary driver of technical debt and makes it difficult to maintain a clear "Source of Truth" for agent behavior.35

### **The Prompt Registry Design Pattern**

A Prompt Registry allows for the central management, versioning, and testing of prompt templates.36 By using Jinja2, developers can create flexible, adaptable templates that incorporate dynamic content like tool descriptions, current file snippets, and conversation history.38

| Feature | Architectural Benefit | Implementation Detail |
| :---- | :---- | :---- |
| Template Inheritance | Ensures consistency across multiple agents | Use {% extends "base.j2" %} to share common instructions 36 |
| Conditional Logic | Dynamically adapts the prompt to the context | {% if task \== "debug" %} Include traceback logic {% endif %} 38 |
| Strict Undefined | Prevents silent failures from missing data | Configure jinja2.Environment with undefined=StrictUndefined 11 |
| Variable Sandboxing | Enhances security of the templating engine | Use jinja2.sandbox.SandboxedEnvironment 40 |

By storing prompts as .j2 files in a dedicated directory, developers can manage them with version control (Git), allowing for clear auditing of how changes to the system instructions affect agent performance.11 Furthermore, using a "Prompt Manager" class ensures that the same prompt structure can be reused across the API, background workers, and evaluation suites, significantly reducing the maintenance overhead.35

### **Token Reduction through Context Pruning and Pruning**

Agentic coding tasks are inherently token-intensive. A ReAct-style agent that re-sends the entire accumulated context with every reasoning step can quickly consume thousands of tokens, leading to high costs and reaching context window limits.41 The architecture should implement context compression techniques to keep prompts efficient.42

Libraries like LLMLingua can achieve up to 20x compression by identifying and removing non-essential tokens from long-form text without losing the core semantic meaning.42 For tool-heavy workloads, the orchestrator should implement "Tool Output Compression," which filters out redundant data from large API responses (e.g., removing metadata fields from a list of files) and prioritizes "statistical outliers" or items that match the user's query via BM25 scoring.44 Using tiktoken to monitor exact token counts ensures that the system can proactively truncate history or trigger a "summarization turn" before the model's attention span is exceeded.41

## **State Management and Durable Execution**

For agentic workflows that involve long-running software engineering tasks—such as a full project refactor or a multi-file bug fix—simple in-memory state is insufficient.45 The system must be able to resume a workflow after infrastructure failures or during long-horizon tasks that require asynchronous human-in-the-loop approval.46

### **Firestore for Persistence vs. Redis for Latency**

GCP offers two primary managed data stores for agent state management, each serving a distinct architectural role.

1. **Cloud Firestore**: As a serverless document database, Firestore is the "safest" choice for persistent agent state. It is ideal for storing conversation history, reasoning chains, and audit logs that must be durable across restarts.45 Firestore's multi-region support and automatic scaling ensure that any instance of the application can retrieve the current state of a session.47  
2. **Memorystore for Redis**: For high-frequency reasoning loops where state lookups must be under 100ms, Redis is the industry standard.45 Agents often make multiple context retrievals during a single task; latency here compounds, potentially causing a noticeable delay for the end-user.49 A hybrid approach—using Redis as a "hot" session cache and Firestore for "cold" storage—offers the best balance of performance and durability.45

### **Workflow Orchestration Frameworks**

Managing complex, stateful transitions is best handled by established orchestration platforms rather than custom-built state machines.50

* **Temporal**: Designed for mission-critical, long-running workflows. It makes application code fault-tolerant by durably persisting the execution state in an "Event History".46 If a Cloud Run instance crashes during an agent's code execution, Temporal will restart the worker and resume the workflow from the exact point of failure, ensuring that the coding task is completed regardless of infrastructure issues.46  
* **LangGraph**: An extension of LangChain specifically for building stateful, multi-actor applications using cyclic graphs.46 It is ideal for agents that need to "loop back" to previous steps (e.g., reflecting on code that failed a test) and allows for granular control over the shared state.46  
* **Prefect \+ ControlFlow**: For teams that prioritize a Python-native experience, Prefect allows for the orchestration of agents using standard decorators.50 It is particularly well-suited for "data-heavy" agentic tasks where the output of the agent (e.g., a codebase analysis report) is treated as a first-class asset.46

| Platform | Core Philosophy | Best Use Case |
| :---- | :---- | :---- |
| Temporal | Durable Execution | Mission-critical, very long-running tasks 46 |
| LangGraph | Cyclic Graph | Stateful agents with frequent feedback loops 46 |
| Prefect | Pythonic Pipeline | ML/Data engineering workflows with agents 50 |
| n8n | Low-Code Workflow | Rapid prototyping of agent-tool integrations 52 |

## **Observability, Tracing, and Monitoring**

The inherent non-determinism of agentic systems makes traditional logging insufficient for debugging and performance tuning.25 Distributed tracing is required to understand why an agent made a specific decision or why a tool call failed.8

### **OpenTelemetry and Structured Logging**

The architecture should implement structured logging (e.g., using structlog) to ensure that all logs are captured in JSON format, facilitating easy analysis in Google Cloud Logging.8 Furthermore, adopting OpenTelemetry as a standardized tracing layer allows telemetry data to flow into any observability stack.8

In an agentic coding project, every LLM interaction should be traced as a "Span," capturing the input prompt, the generated thought process, the tool call parameters, and the final response.53 This "transparency" into the agent's internal reasoning is what allows developers to identify prompt drift or "hallucination hotspots" before they impact the user.53

### **Comparing LLM Observability Tools**

Specialized platforms for 2025 offer features that generic observability tools lack, such as "LLM-as-a-judge" evaluation and cost tracking by token.53

* **LangSmith and Langfuse**: These are "observability-centric" platforms that excel at visualizing request flows and multi-step interactions.51 They provide a "Thread" view that is essential for debugging long-running agent conversations.54  
* **Comet Opik**: Notable for its performance, Opik completes trace logging and evaluation significantly faster than competitors (up to 14x faster than Phoenix), which is critical for maintaining low latency in high-volume applications.53  
* **Arize Phoenix**: Offers "evaluation-centric" observability, focusing on metrics like groundedness and answer relevance to help tune RAG systems and agent tool-use.53

Adopting these tools ensures that the development team has a "system of record" for the agent's performance, enabling data-driven prompt engineering and better infrastructure choices.54

## **Testing, Evaluation, and CI/CD for Agentic Systems**

Testing an agentic system requires a multi-layered approach that combines traditional software testing with specialized LLM evaluation techniques.25

### **Unit Testing and Mocking Strategies**

Following the F.I.R.S.T test principle, unit tests for the agentic orchestrator must be fast and isolated.18 Mocking the LLM response and the file system is critical to achieve this.18

* **MockLLM Server**: An LLM simulator that mimics OpenAI or Anthropic API formats and returns deterministic responses from a YAML configuration file.19 This allows developers to test the "Turn Taking" and "Orchestration" logic without a live internet connection or API costs.2  
* **Mocking Tools, Not Logic**: Best practice dictates mocking the *external dependencies* (the tools) rather than the agent's *core reasoning logic*.58 For example, when testing a "Research Agent," the code should mock the "Web Search Tool" result to ensure that the agent correctly parses and synthesizes the provided data.58

### **Evaluation Frameworks: RAGAS and DeepEval**

To measure the "quality" of the agent's output, deterministic assertions are often impossible.25 Instead, evaluation frameworks use "LLM-as-a-judge" patterns to score responses based on criteria like "Factuality," "Relevance," and "Security".25

* **RAGAS**: Focuses specifically on RAG systems, providing metrics for context precision, context recall, and faithfulness.53  
* **DeepEval**: Offers a comprehensive suite of metrics for agentic systems, including hallucination detection and language mismatch.54 These metrics can be integrated into the CI/CD pipeline, acting as a "quality gate" that prevents the promotion of a new prompt or model version if it causes a regression in performance.25

### **CI/CD on GCP with Docker Bake**

The deployment pipeline should utilize Docker Bake for centralized builds, which allows for simultaneous building of the API, the agent service, and the sandbox proxy.3 By leveraging Artifact Registry caching (cache-to=mode=max), the system can significantly speed up the build process by reusing layers across different services.3

Cloud Build manages the orchestration of the pipeline:

1. **Build and Push**: Building OCI-compliant images for all components.3  
2. **Deploy Agent Service**: Using the adk deploy CLI to push the reasoning loop to Vertex AI Agent Engine.3  
3. **Deploy API Layer**: Pushing the FastAPI service to Cloud Run, ensuring it has the correct IAM roles (e.g., aiplatform.user, bigquery.dataViewer) to interact with GCP services.3

## **Strategic Conclusion**

The architectural design proposed herein addresses the dual requirements of modularity and robustness by anchoring the agentic coding project in proven software engineering principles. By adopting Hexagonal Architecture and a centralized Dependency Injection container, the system achieves a strict separation of concerns that isolates the "Domain" from the volatile nature of LLM frameworks and cloud delivery mechanisms. This decoupling is the primary defense against "agent invention," ensuring that the model operates within a constrained, well-defined environment where its actions are guided by high-fidelity tools and modular prompts.1

The utilization of GCP's managed services—specifically Cloud Run for stateless APIs, Vertex AI Agent Engine for managed reasoning, and gVisor-based sandboxes for secure code execution—provides the infrastructure necessary to scale this system securely.3 The integration of Jinja2 as a "Prompt Source of Truth" and the adoption of modern observability tools like OpenTelemetry ensure that the system is not a "black box" but a transparent, auditable platform.8 Finally, by implementing a rigorous testing and evaluation strategy that uses LLM-as-a-judge patterns, organizations can move from prototype to production with the confidence that their agentic coding system will remain reliable, cost-effective, and secure in the face of evolving model capabilities.25

#### **Works cited**

1. A Lightweight Modular Framework for Constructing Autonomous Agents Driven by Large Language Models: Design, Implementation, and Applications in AgentForge This work is submitted for review to IEEE Access. \- arXiv, accessed March 31, 2026, [https://arxiv.org/html/2601.13383v1](https://arxiv.org/html/2601.13383v1)  
2. Design feedback on a provider-agnostic multi-agent framework in Python \#183019 \- GitHub, accessed March 31, 2026, [https://github.com/orgs/community/discussions/183019](https://github.com/orgs/community/discussions/183019)  
3. End-to-End AI Agent on GCP: ADK, BigQuery MCP, Agent Engine ..., accessed March 31, 2026, [https://medium.com/google-cloud/end-to-end-ai-agent-on-gcp-adk-bigquery-mcp-agent-engine-and-cloud-run-4843fec27c13](https://medium.com/google-cloud/end-to-end-ai-agent-on-gcp-adk-bigquery-mcp-agent-engine-and-cloud-run-4843fec27c13)  
4. What's the best code execution sandbox for AI agents in 2026? | Blog \- Northflank, accessed March 31, 2026, [https://northflank.com/blog/best-code-execution-sandbox-for-ai-agents](https://northflank.com/blog/best-code-execution-sandbox-for-ai-agents)  
5. Secure Code Execution for the Age of Autonomous AI Agents | by Vlad Kolesnikov | Google Cloud \- Community | Feb, 2026 | Medium, accessed March 31, 2026, [https://medium.com/google-cloud/secure-code-execution-for-the-age-of-autonomous-ai-agents-d52e7acd6c5d](https://medium.com/google-cloud/secure-code-execution-for-the-age-of-autonomous-ai-agents-d52e7acd6c5d)  
6. FastAPI Best Practices \- Auth0, accessed March 31, 2026, [https://auth0.com/blog/fastapi-best-practices/](https://auth0.com/blog/fastapi-best-practices/)  
7. I Built a FastAPI \+ Hexagonal Architecture Boilerplate So You Don't ..., accessed March 31, 2026, [https://medium.com/@jimmy.auris.castillejos/i-built-a-fastapi-hexagonal-architecture-boilerplate-so-you-dont-have-to-you-re-welcome-180461a3d6b9](https://medium.com/@jimmy.auris.castillejos/i-built-a-fastapi-hexagonal-architecture-boilerplate-so-you-dont-have-to-you-re-welcome-180461a3d6b9)  
8. Best Practices in FastAPI Architecture: A Complete Guide to Building Scalable, Modern APIs, accessed March 31, 2026, [https://zyneto.com/blog/best-practices-in-fastapi-architecture](https://zyneto.com/blog/best-practices-in-fastapi-architecture)  
9. FastAPI Setup Guide for 2025: Requirements, Structure & Deployment \- DEV Community, accessed March 31, 2026, [https://dev.to/zestminds\_technologies\_c1/fastapi-setup-guide-for-2025-requirements-structure-deployment-1gd](https://dev.to/zestminds_technologies_c1/fastapi-setup-guide-for-2025-requirements-structure-deployment-1gd)  
10. FastAPI Best Practices: A Complete Guide for Building Production-Ready APIs \- Medium, accessed March 31, 2026, [https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617](https://medium.com/@abipoongodi1211/fastapi-best-practices-a-complete-guide-for-building-production-ready-apis-bb27062d7617)  
11. Prompts — NVIDIA AI-Q Blueprint, accessed March 31, 2026, [https://docs.nvidia.com/aiq-blueprint/1.2.1/customization/prompts.html](https://docs.nvidia.com/aiq-blueprint/1.2.1/customization/prompts.html)  
12. Vertex AI Agent Engine Code Execution \- Google Cloud Documentation, accessed March 31, 2026, [https://docs.cloud.google.com/agent-builder/agent-engine/code-execution/overview](https://docs.cloud.google.com/agent-builder/agent-engine/code-execution/overview)  
13. How to Build and Deploy a Multi-Agent AI System with Python and Docker \- freeCodeCamp, accessed March 31, 2026, [https://www.freecodecamp.org/news/build-and-deploy-multi-agent-ai-with-python-and-docker/](https://www.freecodecamp.org/news/build-and-deploy-multi-agent-ai-with-python-and-docker/)  
14. Dependencies \- FastAPI, accessed March 31, 2026, [https://fastapi.tiangolo.com/tutorial/dependencies/](https://fastapi.tiangolo.com/tutorial/dependencies/)  
15. FastAPI Dependency Injection (DI) VS. Depends | Backend APIs, Web Apps, Bots & Automation | Hrekov, accessed March 31, 2026, [https://hrekov.com/blog/fastapi-dependency-injection-vs-depends](https://hrekov.com/blog/fastapi-dependency-injection-vs-depends)  
16. Dependency Injection in Python, Beyond FastAPI's Depends | by Guillaume Launay, accessed March 31, 2026, [https://medium.com/@guillaume.launay/dependency-injection-in-python-beyond-fastapis-depends-eec237b1327b](https://medium.com/@guillaume.launay/dependency-injection-in-python-beyond-fastapis-depends-eec237b1327b)  
17. Benchmarked: 10 Python Dependency Injection libraries vs Manual Wiring (50 rounds x 100k requests) \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/Python/comments/1rkos6s/benchmarked\_10\_python\_dependency\_injection/](https://www.reddit.com/r/Python/comments/1rkos6s/benchmarked_10_python_dependency_injection/)  
18. Importance of Mocking in LLM Streaming through FastApi Python | by eryawww \- Medium, accessed March 31, 2026, [https://medium.com/@zazaneryawan/importance-of-mocking-in-llm-streaming-through-fastapi-python-5092984915d3](https://medium.com/@zazaneryawan/importance-of-mocking-in-llm-streaming-through-fastapi-python-5092984915d3)  
19. GitHub \- StacklokLabs/mockllm: MockLLM, when you want it to do what you tell it to do\!, accessed March 31, 2026, [https://github.com/StacklokLabs/mockllm](https://github.com/StacklokLabs/mockllm)  
20. 7 Practical Design Patterns for Agentic Systems \- MongoDB, accessed March 31, 2026, [https://www.mongodb.com/resources/basics/artificial-intelligence/agentic-systems](https://www.mongodb.com/resources/basics/artificial-intelligence/agentic-systems)  
21. Agent system design patterns | Databricks on AWS, accessed March 31, 2026, [https://docs.databricks.com/aws/en/generative-ai/guide/agent-system-design-patterns](https://docs.databricks.com/aws/en/generative-ai/guide/agent-system-design-patterns)  
22. 7 Must-Know Agentic AI Design Patterns \- MachineLearningMastery.com, accessed March 31, 2026, [https://machinelearningmastery.com/7-must-know-agentic-ai-design-patterns/](https://machinelearningmastery.com/7-must-know-agentic-ai-design-patterns/)  
23. Choose a design pattern for your agentic AI system | Cloud Architecture Center, accessed March 31, 2026, [https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system)  
24. Model Context Protocol architecture patterns for multi-agent AI systems \- IBM Developer, accessed March 31, 2026, [https://developer.ibm.com/articles/mcp-architecture-patterns-ai-systems/](https://developer.ibm.com/articles/mcp-architecture-patterns-ai-systems/)  
25. LLM Testing Strategy: Mocks, Evaluation, and Regression Testing for AI Systems, accessed March 31, 2026, [https://dev.to/myougatheaxo/llm-testing-strategy-mocks-evaluation-and-regression-testing-for-ai-systems-470a](https://dev.to/myougatheaxo/llm-testing-strategy-mocks-evaluation-and-regression-testing-for-ai-systems-470a)  
26. Vertex AI Agent Builder | Google Cloud, accessed March 31, 2026, [https://cloud.google.com/products/agent-builder](https://cloud.google.com/products/agent-builder)  
27. Quickstart: Build and deploy a Python (FastAPI) web app to Cloud Run, accessed March 31, 2026, [https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service](https://docs.cloud.google.com/run/docs/quickstarts/build-and-deploy/deploy-python-fastapi-service)  
28. Code execution in Cloud Run | Google Cloud Documentation, accessed March 31, 2026, [https://docs.cloud.google.com/run/docs/code-execution](https://docs.cloud.google.com/run/docs/code-execution)  
29. Top Python libraries of 2025 \- Tryolabs, accessed March 31, 2026, [https://tryolabs.com/blog/top-python-libraries-2025](https://tryolabs.com/blog/top-python-libraries-2025)  
30. Google MCP Servers Tutorial: Deploying Agentic AI on GCP \- DataCamp, accessed March 31, 2026, [https://www.datacamp.com/tutorial/google-mcp-servers](https://www.datacamp.com/tutorial/google-mcp-servers)  
31. Hybrid AI and LLM-Enabled Agent-Based Real-Time Decision Support Architecture for Industrial Batch Processes: A Clean-in-Place Case Study \- MDPI, accessed March 31, 2026, [https://www.mdpi.com/2673-2688/7/2/51](https://www.mdpi.com/2673-2688/7/2/51)  
32. Sandboxed AI Agent Execution, accessed March 31, 2026, [https://ibl.ai/resources/capabilities/sandboxed-agent-execution](https://ibl.ai/resources/capabilities/sandboxed-agent-execution)  
33. Isolate AI code execution with Agent Sandbox | GKE AI/ML \- Google Cloud Documentation, accessed March 31, 2026, [https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox](https://docs.cloud.google.com/kubernetes-engine/docs/how-to/agent-sandbox)  
34. 5 Code Sandboxes for Your AI Agents \- KDnuggets, accessed March 31, 2026, [https://www.kdnuggets.com/5-code-sandbox-for-your-ai-agents](https://www.kdnuggets.com/5-code-sandbox-for-your-ai-agents)  
35. Building a Git-Based Prompt Versioning System with Python & Jinja | by Ben Batman, accessed March 31, 2026, [https://medium.com/@benbatman2/building-a-git-based-prompt-versioning-system-with-python-jinja-bb1d37d9ee4b](https://medium.com/@benbatman2/building-a-git-based-prompt-versioning-system-with-python-jinja-bb1d37d9ee4b)  
36. Prompt Management Using Jinja. A guide on how Jinja2 templates can be… | by Arunabh Bora | Towards AI, accessed March 31, 2026, [https://pub.towardsai.net/prompt-management-using-jinja-aab5d634d9e2](https://pub.towardsai.net/prompt-management-using-jinja-aab5d634d9e2)  
37. Prompt Registry Overview \- PromptLayer, accessed March 31, 2026, [https://docs.promptlayer.com/features/prompt-registry/overview](https://docs.promptlayer.com/features/prompt-registry/overview)  
38. Prompt\_Engineering/all\_prompt\_engineering\_techniques/prompt-templates-variables-jinja2.ipynb at main \- GitHub, accessed March 31, 2026, [https://github.com/NirDiamant/Prompt\_Engineering/blob/main/all\_prompt\_engineering\_techniques/prompt-templates-variables-jinja2.ipynb](https://github.com/NirDiamant/Prompt_Engineering/blob/main/all_prompt_engineering_techniques/prompt-templates-variables-jinja2.ipynb)  
39. Mastering LLM Prompts with Jinja2: A Practical Guide | Kite Metric, accessed March 31, 2026, [https://kitemetric.com/blogs/building-smarter-prompts-for-llms-with-jinja2](https://kitemetric.com/blogs/building-smarter-prompts-for-llms-with-jinja2)  
40. Prompt Templating with Jinja \- Dynamic Prompt Generation \- Instructor, accessed March 31, 2026, [https://python.useinstructor.com/concepts/templating/](https://python.useinstructor.com/concepts/templating/)  
41. Context Compression Techniques: Reduce LLM Costs by 50% \- SitePoint, accessed March 31, 2026, [https://www.sitepoint.com/optimizing-token-usage-context-compression-techniques/](https://www.sitepoint.com/optimizing-token-usage-context-compression-techniques/)  
42. How to Compress Your Prompts and Reduce LLM Costs \- freeCodeCamp, accessed March 31, 2026, [https://www.freecodecamp.org/news/how-to-compress-your-prompts-and-reduce-llm-costs/](https://www.freecodecamp.org/news/how-to-compress-your-prompts-and-reduce-llm-costs/)  
43. LLM Compression Techniques to Build Faster and Cheaper LLMs \- ProjectPro, accessed March 31, 2026, [https://www.projectpro.io/article/llm-compression/1179](https://www.projectpro.io/article/llm-compression/1179)  
44. Tool output compression for agents \- 60-70% token reduction on tool-heavy workloads (open source, works with local models) : r/LocalLLaMA \- Reddit, accessed March 31, 2026, [https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool\_output\_compression\_for\_agents\_6070\_token/](https://www.reddit.com/r/LocalLLaMA/comments/1qbei13/tool_output_compression_for_agents_6070_token/)  
45. State Management Patterns for Long-Running AI Agents: Redis vs StatefulSets vs External Databases | by inboryn | Medium, accessed March 31, 2026, [https://medium.com/@inboryn/state-management-patterns-for-long-running-ai-agents-redis-vs-statefulsets-vs-external-databases-58eb0a16d617](https://medium.com/@inboryn/state-management-patterns-for-long-running-ai-agents-redis-vs-statefulsets-vs-external-databases-58eb0a16d617)  
46. Kinde Orchestrating Multi-Step Agents: Temporal/Dagster ..., accessed March 31, 2026, [https://kinde.com/learn/ai-for-software-engineering/ai-devops/orchestrating-multi-step-agents-temporal-dagster-langgraph-patterns-for-long-running-work/](https://kinde.com/learn/ai-for-software-engineering/ai-devops/orchestrating-multi-step-agents-temporal-dagster-langgraph-patterns-for-long-running-work/)  
47. Best practices for Cloud Firestore \- Firebase \- Google, accessed March 31, 2026, [https://firebase.google.com/docs/firestore/best-practices](https://firebase.google.com/docs/firestore/best-practices)  
48. How to Migrate Stateful Workloads to Stateless Microservices \- OneUptime, accessed March 31, 2026, [https://oneuptime.com/blog/post/2026-02-17-how-to-migrate-stateful-workloads-to-stateless-microservices-using-cloud-firestore-on-gcp/view](https://oneuptime.com/blog/post/2026-02-17-how-to-migrate-stateful-workloads-to-stateless-microservices-using-cloud-firestore-on-gcp/view)  
49. How to Build AI Agents with Redis Memory Management, accessed March 31, 2026, [https://redis.io/blog/build-smarter-ai-agents-manage-short-term-and-long-term-memory-with-redis/](https://redis.io/blog/build-smarter-ai-agents-manage-short-term-and-long-term-memory-with-redis/)  
50. Kestra vs Temporal vs Prefect: Choosing Your Workflow Orchestration Platform (2025), accessed March 31, 2026, [https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/](https://procycons.com/en/blogs/workflow-orchestration-platforms-comparison-2025/)  
51. 9 Best LLM Orchestration Frameworks for Agents and RAG \- ZenML Blog, accessed March 31, 2026, [https://www.zenml.io/blog/best-llm-orchestration-frameworks](https://www.zenml.io/blog/best-llm-orchestration-frameworks)  
52. Top Agentic AI Frameworks in 2025: Which One Fits Your Needs? \- Medium, accessed March 31, 2026, [https://medium.com/data-science-collective/top-agentic-ai-frameworks-in-2025-which-one-fits-your-needs-0eb95dcd7c58](https://medium.com/data-science-collective/top-agentic-ai-frameworks-in-2025-which-one-fits-your-needs-0eb95dcd7c58)  
53. Best LLM Observability Tools of 2025: Top Platforms & Features \- Comet, accessed March 31, 2026, [https://www.comet.com/site/blog/llm-observability-tools/](https://www.comet.com/site/blog/llm-observability-tools/)  
54. Top 10 LLM observability tools: Complete guide for 2025 \- Articles \- Braintrust, accessed March 31, 2026, [https://www.braintrust.dev/articles/top-10-llm-observability-tools-2025](https://www.braintrust.dev/articles/top-10-llm-observability-tools-2025)  
55. Top 9 LLM Observability Tools in 2025 \- Logz.io, accessed March 31, 2026, [https://logz.io/blog/top-llm-observability-tools/](https://logz.io/blog/top-llm-observability-tools/)  
56. 10 Best LLM Monitoring Tools to Use in 2025 (Ranked & Reviewed) \- ZenML Blog, accessed March 31, 2026, [https://www.zenml.io/blog/best-llm-monitoring-tools](https://www.zenml.io/blog/best-llm-monitoring-tools)  
57. ProjectTest: A Project-level LLM Unit Test Generation Benchmark and Impact of Error Fixing Mechanisms \- arXiv, accessed March 31, 2026, [https://arxiv.org/html/2502.06556v3](https://arxiv.org/html/2502.06556v3)  
58. Mocking External APIs in Agent Tests – Scenario \- LangWatch, accessed March 31, 2026, [https://langwatch.ai/scenario/testing-guides/mocks/](https://langwatch.ai/scenario/testing-guides/mocks/)  
59. Asynchronous invocation of agentic AI application using events \- Google Codelabs, accessed March 31, 2026, [https://codelabs.developers.google.com/codelabs/genai/agents/async-invocation-with-adk](https://codelabs.developers.google.com/codelabs/genai/agents/async-invocation-with-adk)
