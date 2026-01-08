import os
import json
import sqlite3
from google import genai
from concurrent.futures import ThreadPoolExecutor

GEMINI_API_KEY = "AIzaSyAtCpTmcvWqdak9tg_WmKWhkpY0AB2jX18"
DATABASE_NAME = "setup.db"

def generate_search_queries(user_input: str) -> list:
    """
    Uses Gemini to identify the core product category and reliable, broad keywords
    to ensure database results are found for analysis.
    """
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Gemini Client Initialization Failed: {e}. Using safe default keywords.")
        return ["Phone", "Budget Phone", "Infinix Tecno"]

    prompt = f"""
    The user's request is: "{user_input}".
    
    1. Determine the single most appropriate product category (e.g., Phone, Laptop, Tool) from the inventory.
    2. Generate a list of 3 searchable keywords. This list MUST start with the exact category name found in step 1.
    3. The remaining two keywords should be broad, descriptive terms based on the user's request (e.g., 'cheap', 'reliable').
    4. The output must be a clean JSON array of strings. Example: ["Phone", "budget", "reliable"].
    """
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        text_response = response.text.strip().strip("```json").strip("```")
        
        try:
            keywords = json.loads(text_response)
        except json.JSONDecodeError:
            print("Warning: Gemini returned malformed JSON. Using fallback keywords.")
            keywords = ["Phone", "budget", "reliable"]
            
        return keywords
        
    except Exception as e:
        print(f"Gemini Query Generation Failed: {e}. Using safe default keywords.")
        return ["Phone", "budget", "reliable"]

def fetch_db_results(query_keyword: str) -> dict:
    """
    Queries the local database for products matching a keyword, falling back to 
    a category search if the keyword is generic (like 'phone' or 'laptop').
    """
    print(f"🔎 Searching Database for: '{query_keyword}'")
    
    conn = None
    try:
        conn = sqlite3.connect(DATABASE_NAME)
        cursor = conn.cursor()
        
        search_term = f'%{query_keyword}%'
        
        sql_query = """
            SELECT category, name, description, price_cfa, image_url 
            FROM products 
            WHERE (name LIKE ? OR description LIKE ?) AND price_cfa BETWEEN 5000 AND 800000
            LIMIT 5;
        """
        cursor.execute(sql_query, (search_term, search_term))
        results = cursor.fetchall()
        
        if not results:
            category_keyword = query_keyword.split()[0].title()
            print(f"    ➡️ Fallback: Searching by category '{category_keyword}'")
            
            sql_fallback = """
                SELECT category, name, description, price_cfa, image_url 
                FROM products 
                WHERE category LIKE ? AND price_cfa BETWEEN 5000 AND 800000
                LIMIT 5;
            """
            cursor.execute(sql_fallback, (f'%{category_keyword}%',))
            results = cursor.fetchall()


        items = []
        for row in results:
            items.append({
                'category': row[0],
                'name': row[1],
                'description': row[2],
                'price_cfa': row[3],
                'imageUrl': row[4]
            })

        return {'query': query_keyword, 'items': items}
        
    except sqlite3.Error as e:
        return {'query': query_keyword, 'error': f'Database Error: {e}'}
    finally:
        if conn:
            conn.close()

def run_concurrent_db_searches(queries: list) -> list:
    print("\n--- Starting Concurrent Database Searches ---")
    all_results = []
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(fetch_db_results, q): q for q in queries}
        
        for future in futures:
            all_results.append(future.result())
            
    print("--- All searches complete. ---")
    return all_results

def analyze_and_summarize_results(raw_search_data: list, user_request: str) -> str:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        return f"\nAnalysis Skipped: Gemini Client Initialization Failed: {e}"

    data_string = json.dumps(raw_search_data, indent=2)
    
    prompt = f"""
    Analyze the following raw database results. The user's original request was: "{user_request}".
    
    1. Determine the appropriate product category (e.g., Laptop, Tool, Phone) based on the user request.
    2. Identify the single BEST product from the search results that matches the user's need 
       (e.g., best value for the budget, or best fit for the function like 'making holes').
    3. Provide the product name, its price, and the specific image URL.
    4. Provide a brief, convincing description (2-3 sentences) explaining why this is the best option.
    5. Output the result in a clean, human-readable Markdown format.
    
    RAW DATABASE RESULTS:
    {data_string}
    """
    
    print("\n🧠 Sending data to Gemini for final analysis and summary...")
    
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        return response.text
    except Exception as e:
        return f"Gemini Analysis Failed: {e}"

if __name__ == "__main__":
    
    user_query = "i need a phone of 80,000"

    if not os.path.exists(DATABASE_NAME):
        print(f"\nFATAL ERROR: Database file '{DATABASE_NAME}' not found.")
        print("Please run the 'setup_db.py' script once to create the database.")
    elif GEMINI_API_KEY == "YOUR_FULL_GEMINI_API_KEY_HERE":
        print("\nFATAL ERROR: Please replace the placeholder API keys in the code with your actual credentials.")
    else:
        print(f"User Request: {user_query}")
        
        search_keywords = generate_search_queries(user_query)
        print(f"Generated Search Keywords: {search_keywords}")
        
        raw_db_data = run_concurrent_db_searches(search_keywords)
        
        final_recommendation = analyze_and_summarize_results(raw_db_data, user_query)
        
        print("\n\n==============================================")
        print("      FINAL BEST PRODUCT RECOMMENDATION       ")
        print("==============================================")
        print(final_recommendation)
        print("==============================================")