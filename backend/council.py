"""3-stage LLM Council orchestration."""

from typing import List, Dict, Any, Tuple
import asyncio
import json
from .openrouter import query_model
from .config import PERSONAS, DEFAULT_PERSONAS, CHAIRMAN_MODEL


async def generate_dynamic_personas(user_query: str) -> List[Dict[str, str]]:
    """
    Generate a list of relevant personas based on the user query.
    
    Args:
        user_query: The user's question
        
    Returns:
        List of dicts with 'id', 'name', 'role', 'icon', 'style', 'system_prompt', 'model'
    """
    prompt = f"""You are the Chairman of an AI Council. Your job is to assemble a team of 3-5 expert personas to answer the following question.
    
    Question: "{user_query}"
    
    Identify the most relevant perspectives or roles needed to provide a comprehensive, diverse, and high-quality answer.
    For example:
    - If the question is about business, you might need a "Legal Expert", "Sales Strategist", and "Product Manager".
    - If the question is about coding, you might need a "Senior Architect", "Security Specialist", and "Performance Engineer".
    - Always include at least one critical or alternative perspective (e.g., "Devil's Advocate", "Skeptic", "Ethicist").
    
    Return the result as a JSON object with a "personas" key containing a list of objects. Each object must have:
    - "id": A unique short identifier (e.g., "legal_expert")
    - "name": Display name (e.g., "Legal Expert")
    - "role": Short role description (e.g., "Corporate Law Specialist")
    - "icon": A single emoji representing the persona
    - "style": A short description of their tone/style (e.g., "formal, cautious, precise")
    - "system_prompt": A detailed system prompt that instructs the AI how to behave as this persona.
    - "model": The LLM model to use (choose from: "openai/gpt-5.1", "anthropic/claude-sonnet-4.5", "google/gemini-3-pro-preview", "x-ai/grok-4"). Assign the most appropriate model for the role.
    
    JSON Response:"""
    
    messages = [{"role": "user", "content": prompt}]
    
    # Use a smart model for this planning step
    response = await query_model(CHAIRMAN_MODEL, messages)
    
    if not response or not response.get('content'):
        # Fallback to default personas if generation fails
        return [
            {**PERSONAS[pid], "id": pid} for pid in DEFAULT_PERSONAS if pid in PERSONAS
        ]
        
    try:
        content = response['content']
        # Clean up markdown code blocks if present
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
            
        data = json.loads(content.strip())
        return data.get("personas", [])
    except Exception as e:
        print(f"Error parsing dynamic personas: {e}")
        # Fallback
        return [
            {**PERSONAS[pid], "id": pid} for pid in DEFAULT_PERSONAS if pid in PERSONAS
        ]


async def stage1_collect_responses(user_query: str, personas: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Stage 1: Collect individual responses from selected personas.

    Args:
        user_query: The user's question
        personas: List of persona objects to consult

    Returns:
        List of dicts with 'persona_id', 'model', 'response', etc.
    """
    # Create tasks for each persona
    tasks = []
    
    for persona in personas:
        messages = [
            {"role": "system", "content": persona["system_prompt"]},
            {"role": "user", "content": user_query}
        ]
        
        tasks.append(query_model(persona["model"], messages))

    # Query all models in parallel
    responses = await asyncio.gather(*tasks)

    # Format results
    stage1_results = []
    for persona, response in zip(personas, responses):
        if response is not None:  # Only include successful responses
            stage1_results.append({
                "persona_id": persona["id"],
                "persona_name": persona["name"],
                "persona_role": persona["role"],
                "persona_icon": persona["icon"],
                "model": persona["model"],
                "response": response.get('content', '')
            })

    return stage1_results


async def stage2_collect_rankings(
    user_query: str,
    stage1_results: List[Dict[str, Any]]
) -> Tuple[List[Dict[str, Any]], Dict[str, str]]:
    """
    Stage 2: Each model ranks the anonymized responses.

    Args:
        user_query: The original user query
        stage1_results: Results from Stage 1

    Returns:
        Tuple of (rankings list, label_to_persona mapping)
    """
    # Create anonymized labels for responses (Response A, Response B, etc.)
    labels = [chr(65 + i) for i in range(len(stage1_results))]  # A, B, C, ...

    # Create mapping from label to persona name (for display)
    label_to_persona = {
        f"Response {label}": result['persona_name']
        for label, result in zip(labels, stage1_results)
    }

    # Build the ranking prompt
    responses_text = "\n\n".join([
        f"Response {label}:\n{result['response']}"
        for label, result in zip(labels, stage1_results)
    ])

    ranking_prompt = f"""You are evaluating different responses to the following question:

Question: {user_query}

Here are the responses from different perspectives (anonymized):

{responses_text}

Your task:
1. First, evaluate each response individually. For each response, explain what it does well and what it does poorly.
2. Then, at the very end of your response, provide a final ranking.

IMPORTANT: Your final ranking MUST be formatted EXACTLY as follows:
- Start with the line "FINAL RANKING:" (all caps, with colon)
- Then list the responses from best to worst as a numbered list
- Each line should be: number, period, space, then ONLY the response label (e.g., "1. Response A")
- Do not add any other text or explanations in the ranking section

Example of the correct format for your ENTIRE response:

Response A provides good detail on X but misses Y...
Response B is accurate but lacks depth on Z...
Response C offers the most comprehensive answer...

FINAL RANKING:
1. Response C
2. Response A
3. Response B

Now provide your evaluation and ranking:"""

    messages = [{"role": "user", "content": ranking_prompt}]

    # Get rankings from all participating models in parallel
    # We use the same models that generated the responses to also rank them
    # This ensures the "Council" is ranking itself
    tasks = []
    ranking_models = []
    
    for result in stage1_results:
        model = result['model']
        ranking_models.append(result['persona_name']) # Track who is ranking
        tasks.append(query_model(model, messages))

    responses = await asyncio.gather(*tasks)

    # Format results
    stage2_results = []
    for ranker_name, response in zip(ranking_models, responses):
        if response is not None:
            full_text = response.get('content', '')
            parsed = parse_ranking_from_text(full_text)
            stage2_results.append({
                "model": ranker_name, # Using persona name as the "model" identifier for display
                "ranking": full_text,
                "parsed_ranking": parsed
            })

    return stage2_results, label_to_persona


async def stage3_synthesize_final(
    user_query: str,
    stage1_results: List[Dict[str, Any]],
    stage2_results: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Stage 3: Chairman synthesizes final response.

    Args:
        user_query: The original user query
        stage1_results: Individual model responses from Stage 1
        stage2_results: Rankings from Stage 2

    Returns:
        Dict with 'model' and 'response' keys
    """
    # Build comprehensive context for chairman
    stage1_text = "\n\n".join([
        f"Persona: {result['persona_name']} ({result['persona_icon']})\nResponse: {result['response']}"
        for result in stage1_results
    ])

    stage2_text = "\n\n".join([
        f"Ranker: {result['model']}\nRanking: {result['ranking']}"
        for result in stage2_results
    ])

    chairman_prompt = f"""You are the Chairman of an LLM Council. Multiple AI Experts (Personas) have provided responses to a user's question, and then ranked each other's responses.

Original Question: {user_query}

STAGE 1 - Expert Responses:
{stage1_text}

STAGE 2 - Peer Rankings:
{stage2_text}

Your task as Chairman is to synthesize all of this information into a single, comprehensive, accurate answer to the user's original question. Consider:
- The individual responses and their unique perspectives
- The peer rankings and what they reveal about response quality
- Any patterns of agreement or disagreement

Provide a clear, well-reasoned final answer that represents the council's collective wisdom:"""

    messages = [{"role": "user", "content": chairman_prompt}]

    # Query the chairman model
    response = await query_model(CHAIRMAN_MODEL, messages)

    if response is None:
        # Fallback if chairman fails
        return {
            "model": "Chairman",
            "response": "Error: Unable to generate final synthesis."
        }

    return {
        "model": "Chairman",
        "response": response.get('content', '')
    }


def parse_ranking_from_text(ranking_text: str) -> List[str]:
    """
    Parse the FINAL RANKING section from the model's response.

    Args:
        ranking_text: The full text response from the model

    Returns:
        List of response labels in ranked order
    """
    import re

    # Look for "FINAL RANKING:" section
    if "FINAL RANKING:" in ranking_text:
        # Extract everything after "FINAL RANKING:"
        parts = ranking_text.split("FINAL RANKING:")
        if len(parts) >= 2:
            ranking_section = parts[1]
            # Try to extract numbered list format (e.g., "1. Response A")
            # This pattern looks for: number, period, optional space, "Response X"
            numbered_matches = re.findall(r'\d+\.\s*Response [A-Z]', ranking_section)
            if numbered_matches:
                # Extract just the "Response X" part
                return [re.search(r'Response [A-Z]', m).group() for m in numbered_matches]

            # Fallback: Extract all "Response X" patterns in order
            matches = re.findall(r'Response [A-Z]', ranking_section)
            return matches

    # Fallback: try to find any "Response X" patterns in order
    matches = re.findall(r'Response [A-Z]', ranking_text)
    return matches


def calculate_aggregate_rankings(
    stage2_results: List[Dict[str, Any]],
    label_to_persona: Dict[str, str]
) -> List[Dict[str, Any]]:
    """
    Calculate aggregate rankings across all models.

    Args:
        stage2_results: Rankings from each model
        label_to_persona: Mapping from anonymous labels to persona names

    Returns:
        List of dicts with model name and average rank, sorted best to worst
    """
    from collections import defaultdict

    # Track positions for each model
    model_positions = defaultdict(list)

    for ranking in stage2_results:
        ranking_text = ranking['ranking']

        # Parse the ranking from the structured format
        parsed_ranking = parse_ranking_from_text(ranking_text)

        for position, label in enumerate(parsed_ranking, start=1):
            if label in label_to_persona:
                persona_name = label_to_persona[label]
                model_positions[persona_name].append(position)

    # Calculate average position for each model
    aggregate = []
    for model, positions in model_positions.items():
        if positions:
            avg_rank = sum(positions) / len(positions)
            aggregate.append({
                "model": model,
                "average_rank": round(avg_rank, 2),
                "rankings_count": len(positions)
            })

    # Sort by average rank (lower is better)
    aggregate.sort(key=lambda x: x['average_rank'])

    return aggregate


async def generate_conversation_title(user_query: str) -> str:
    """
    Generate a short title for a conversation based on the first user message.

    Args:
        user_query: The first user message

    Returns:
        A short title (3-5 words)
    """
    title_prompt = f"""Generate a very short title (3-5 words maximum) that summarizes the following question.
The title should be concise and descriptive. Do not use quotes or punctuation in the title.

Question: {user_query}

Title:"""

    messages = [{"role": "user", "content": title_prompt}]

    # Use gemini-2.5-flash for title generation (fast and cheap)
    response = await query_model("google/gemini-2.5-flash", messages, timeout=30.0)

    if response is None:
        # Fallback to a generic title
        return "New Conversation"

    title = response.get('content', 'New Conversation').strip()

    # Clean up the title - remove quotes, limit length
    title = title.strip('"\'')

    # Truncate if too long
    if len(title) > 50:
        title = title[:47] + "..."

    return title


async def generate_direct_reply(
    persona: Dict[str, Any],
    history: List[Dict[str, Any]],
    user_input: str
) -> Dict[str, Any]:
    """
    Generate a direct reply from a specific persona.

    Args:
        persona: The persona object (name, role, system_prompt, model, etc.)
        history: Previous conversation messages
        user_input: The user's reply content

    Returns:
        Dict with 'response', 'persona_name', etc.
    """
    # Construct messages for the model
    messages = [{"role": "system", "content": persona["system_prompt"]}]
    
    # Add relevant history (simplified for now)
    # In a real app, we'd carefully select context. 
    # Here we just add the last few messages to give context.
    for msg in history[-5:]:
        if msg["role"] == "user":
            messages.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            # If it's a full council response, maybe just show the synthesis?
            # Or if it's a direct reply, show that.
            # For simplicity, let's just add the user input as the main context
            pass

    messages.append({"role": "user", "content": user_input})

    response = await query_model(persona["model"], messages)
    
    return {
        "response": response["content"] if response else "I'm speechless.",
        "persona_name": persona["name"],
        "persona_role": persona["role"],
        "persona_icon": persona["icon"],
        "model": persona["model"]
    }


async def run_full_council(user_query: str) -> Tuple[List, List, List, Dict, Dict]:
    """
    Run the complete 3-stage council process with dynamic personas.

    Args:
        user_query: The user's question

    Returns:
        Tuple of (personas, stage1_results, stage2_results, stage3_result, metadata)
    """
    # Step 0: Generate Dynamic Personas
    personas = await generate_dynamic_personas(user_query)
    
    # Stage 1: Collect individual responses
    stage1_results = await stage1_collect_responses(user_query, personas)

    # If no models responded successfully, return error
    if not stage1_results:
        return personas, [], [], {
            "model": "error",
            "response": "All models failed to respond. Please try again."
        }, {}

    # Stage 2: Collect rankings
    stage2_results, label_to_persona = await stage2_collect_rankings(user_query, stage1_results)

    # Calculate aggregate rankings
    aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_persona)

    # Stage 3: Synthesize final answer
    stage3_result = await stage3_synthesize_final(
        user_query,
        stage1_results,
        stage2_results
    )

    # Prepare metadata
    metadata = {
        "label_to_model": label_to_persona, # Keeping key name for frontend compatibility for now
        "aggregate_rankings": aggregate_rankings
    }

    return personas, stage1_results, stage2_results, stage3_result, metadata
