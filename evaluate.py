import os
import json
import time
from openai import OpenAI
from datasets import load_dataset
from tqdm import tqdm

# --- Configuration ---

# Environment Variables Setup:
# For Judge Model (GPT-4o):
#   export JUDGE_API_KEY="your_openai_api_key"
#   export JUDGE_BASE_URL="https://api.openai.com/v1"  # Optional, defaults to OpenAI
#
# For Test Model:
#   export TEST_MODEL_API_KEY="your_test_model_api_key"  # Optional if same as judge
#   export TEST_MODEL_BASE_URL="your_test_model_endpoint"  # Optional, defaults to OpenAI
#
# If both models use the same credentials, you can just set OPENAI_API_KEY

# 1. Judge Model Configuration (GPT-4o for evaluation)
# The judge model requires OpenAI API access for GPT-4o
JUDGE_API_KEY = os.getenv("JUDGE_API_KEY") or os.getenv("OPENAI_API_KEY")
if not JUDGE_API_KEY:
    raise ValueError("Judge API key not found. Please set JUDGE_API_KEY or OPENAI_API_KEY environment variable.")

JUDGE_BASE_URL = os.getenv("JUDGE_BASE_URL", "https://api.openai.com/v1")
JUDGE_MODEL = "gpt-4o"  # The powerful model that will act as the evaluator

# 2. Model Under Test Configuration  
# Configure these for the model you want to evaluate
TEST_MODEL_API_KEY = os.getenv("TEST_MODEL_API_KEY")
TEST_MODEL_BASE_URL = os.getenv("TEST_MODEL_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
TEST_MODEL_NAME = "gemini-2.0.-flash"  # The actual model being tested
MODEL_UNDER_TEST_NAME = "gemini_2.0_flash_v1"  # Label for results file 

# 3. Dataset Configuration
# The name of your dataset on the Hugging Face Hub.
DATASET_NAME = "CraneAILabs/UCCB" # The UCCB dataset on HuggingFace Hub
DATASET_SPLIT = "test" # Use 'validation' or 'test' split for evaluation

# 4. Output Configuration
RESULTS_FILE_PATH = f"evaluation_results_{MODEL_UNDER_TEST_NAME}.json"

# --- Model Under Test ---

def get_model_response(question: str, test_client: OpenAI) -> str:
    """
    *** THIS IS THE FUNCTION YOU NEED TO EDIT ***
    
    This function takes a question and should return the generated answer from the LLM you want to evaluate.
    
    Args:
        question: The question string from the UCCB dataset.
        test_client: An initialized OpenAI client for the model under test.
        
    Returns:
        The generated answer as a string.
    """
    # Placeholder implementation: 
    # This example uses the configured test model.
    # Replace this section with the API call to YOUR model.
    try:
        # Example: If you are testing another OpenAI-compatible model
        response = test_client.chat.completions.create(
            model=TEST_MODEL_NAME,  # Uses the configured test model
            messages=[
                {"role": "system", "content": "You are a helpful assistant knowledgeable about Ugandan culture."},
                {"role": "user", "content": question}
            ],
            temperature=0.7,
            max_tokens=250
        )
        return response.choices[0].message.content

    except Exception as e:
        print(f"Error getting response from model under test: {e}")
        return "Error: Could not generate a response."


# --- LLM-as-a-Judge ---

def get_judge_evaluation(question: str, reference_answer: str, model_answer: str, judge_client: OpenAI) -> dict:
    """
    Uses a powerful LLM (the "judge") to evaluate the model's answer against the reference answer.
    
    Args:
        question: The original question.
        reference_answer: The ground-truth answer from the UCCB dataset.
        model_answer: The answer generated by the model under test.
        judge_client: The OpenAI client for the judge model (GPT-4o).
        
    Returns:
        A dictionary containing the score and justification.
    """
    # This is the core prompt that defines the evaluation rubric.
    judge_prompt = f"""
    You are an expert evaluator for the Ugandan Cultural Context Benchmark (UCCB). Your task is to assess a model's generated answer based on a ground-truth reference answer.

    **Evaluation Criteria:**
    1.  **Accuracy (Weight: 50%):** Is the information factually correct and directly addressing the question?
    2.  **Cultural Nuance (Weight: 30%):** Does the answer demonstrate an understanding of the specific Ugandan cultural context, including local terminology, social dynamics, and historical subtleties?
    3.  **Completeness & Relevance (Weight: 20%):** Is the answer complete, on-topic, and free of irrelevant information?

    **Scoring Rubric:**
    - **Score 5 (Excellent):** The answer is fully accurate, demonstrates deep cultural nuance, and is perfectly relevant and complete. It is as good as or better than the reference answer.
    - **Score 4 (Good):** The answer is factually correct and relevant but may lack some of the deeper cultural nuance or completeness of the reference answer.
    - **Score 3 (Acceptable):** The answer is generally correct but contains minor inaccuracies or omissions. It understands the question but the answer is superficial.
    - **Score 2 (Poor):** The answer contains significant factual inaccuracies or demonstrates a clear lack of cultural understanding. It may be only partially relevant.
    - **Score 1 (Very Poor):** The answer is completely incorrect, irrelevant, or nonsensical.

    **Task:**
    Evaluate the "Generated Answer" for the given "Question" in comparison to the "Reference Answer". Provide your evaluation in a valid JSON format with two keys: "score" (an integer from 1 to 5) and "justification" (a brief explanation for your score).

    ---
    **Question:**
    {question}

    **Reference Answer:**
    {reference_answer}

    **Generated Answer:**
    {model_answer}
    ---

    **Your JSON Evaluation:**
    """
    
    try:
        response = judge_client.chat.completions.create(
            model=JUDGE_MODEL,
            messages=[{"role": "user", "content": judge_prompt}],
            response_format={"type": "json_object"},
            temperature=0.7,
        )
        evaluation_json = json.loads(response.choices[0].message.content)
        return evaluation_json
    except Exception as e:
        print(f"Error during judging: {e}")
        return {"score": 0, "justification": f"An error occurred during evaluation: {e}"}

# --- Main Execution Logic ---

def main():
    """
    Main function to run the evaluation pipeline.
    """
    print("--- UCCB LLM-as-a-Judge Evaluation Script ---")
    
    # 1. Initialize API Clients
    # Separate clients for judge and test models
    judge_client = OpenAI(api_key=JUDGE_API_KEY, base_url=JUDGE_BASE_URL)
    
    # Initialize test model client (may require different credentials)
    if TEST_MODEL_API_KEY:
        test_client = OpenAI(api_key=TEST_MODEL_API_KEY, base_url=TEST_MODEL_BASE_URL)
    else:
        print("Warning: TEST_MODEL_API_KEY not provided. Using judge client for test model.")
        test_client = judge_client
    
    print(f"Judge Model: {JUDGE_MODEL} (Base URL: {JUDGE_BASE_URL})")
    print(f"Test Model: {TEST_MODEL_NAME} (Base URL: {TEST_MODEL_BASE_URL})")
    print(f"Model Under Test Label: {MODEL_UNDER_TEST_NAME}")

    # 2. Load the Dataset
    try:
        print(f"Loading dataset '{DATASET_NAME}' from Hugging Face Hub...")
        dataset = load_dataset(DATASET_NAME, split=DATASET_SPLIT)
        print(f"Successfully loaded {len(dataset)} items from the '{DATASET_SPLIT}' split.")
    except Exception as e:
        print(f"Error loading dataset: {e}")
        print("Please ensure the dataset name is correct and you are logged into Hugging Face if it's a private repo.")
        return

    # 3. Run Evaluation Loop
    evaluation_results = []
    total_score = 0
    
    for item in tqdm(dataset, desc="Evaluating"):
        question = item.get("question")
        reference_answer = item.get("answer")
        
        if not question or not reference_answer:
            continue

        # Get the response from the model being tested
        model_answer = get_model_response(question, test_client)
        
        # Get the evaluation from the judge model
        evaluation = get_judge_evaluation(question, reference_answer, model_answer, judge_client)
        
        # Store the results
        result_entry = {
            "id": item.get("id"),
            "category": item.get("category"),
            "question": question,
            "reference_answer": reference_answer,
            "model_answer": model_answer,
            "judge_score": evaluation.get("score"),
            "judge_justification": evaluation.get("justification")
        }
        evaluation_results.append(result_entry)
        total_score += evaluation.get("score", 0)
        
        # Respect rate limits
        time.sleep(1) 

    # 4. Calculate and Display Final Score
    if evaluation_results:
        average_score = total_score / len(evaluation_results)
        print("\n--- Evaluation Complete ---")
        print(f"Average Score for '{MODEL_UNDER_TEST_NAME}': {average_score:.2f} / 5.0")
    else:
        print("\n--- No results to evaluate. ---")

    # 5. Save Detailed Results
    with open(RESULTS_FILE_PATH, 'w', encoding='utf-8') as f:
        json.dump(evaluation_results, f, ensure_ascii=False, indent=2)
    print(f"Detailed results saved to: {RESULTS_FILE_PATH}")


if __name__ == "__main__":
    main()

