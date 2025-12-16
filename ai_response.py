import os
import google.generativeai as genai
import time

# Allow a local, untracked secrets file on devices (e.g., Raspberry Pi).
# The file `secrets_local.py` should define `GEMINI_KEY = 'your-key'`.
def _ensure_api_key():
    """Ensure `api_key` is set and genai is configured.
    This attempts the following (in order):
    - `GEMINI_KEY` environment variable
    - `secrets_local.py` file in the working directory
    If found, configure the `genai` client and return the key, otherwise None.
    """
    key = os.environ.get('GEMINI_KEY')
    if key:
        try:
            genai.configure(api_key=key)
        except Exception:
            pass
        return key

    # Try local file fallback dynamically (works if file is created after import)
    try:
        import importlib
        spec = importlib.util.find_spec('secrets_local')
        if spec is not None:
            secrets_local = importlib.import_module('secrets_local')
            key = getattr(secrets_local, 'GEMINI_KEY', None)
            if key:
                try:
                    genai.configure(api_key=key)
                except Exception:
                    pass
                return key
    except Exception:
        pass

    return None


# Determine api_key at import time if possible
api_key = _ensure_api_key()

if api_key:
    print(f"✅ Gemini API Key Found: {str(api_key)[:8]}...")
else:
    print("❌ Warning: GEMINI_KEY environment variable not set and no local secret found. AI responses will not work.")

def get_response(payload: str):
    """Legacy function - redirects to get_chat_response"""
    return get_chat_response(payload)


def get_chat_response(payload: str):
    """Get AI response using Google Gemini"""
    # Ensure we have a valid API key at call time (pick up secrets_local.py if added later)
    key = api_key or _ensure_api_key()
    if not key:
        return {"error": "Gemini API key not configured"}
    
    try:
        # (Re)configure genai with the discovered key to be safe
        try:
            genai.configure(api_key=key)
        except Exception:
            pass

        model = genai.GenerativeModel(
            'gemini-2.5-flash',
            system_instruction=("You are OMNIS, a helpful school assistant robot. "
                                "Keep answers brief and concise. "
                                "Be friendly and to the point."),
        )

        # Allow token tuning via env var for Pi or testing
        max_tokens = int(os.environ.get('GEMINI_MAX_TOKENS', '300'))
        temperature = float(os.environ.get('GEMINI_TEMPERATURE', '0.6'))

        # Try a couple times if the model returns empty content
        response = None
        content = None
        for attempt in range(2):
            try:
                response = model.generate_content(
                    payload,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=temperature,
                    )
                )
            except Exception as e:
                # transient error -> retry once
                if attempt == 0:
                    if os.environ.get('OMNIS_DEBUG') == '1':
                        print(f"[DEBUG] Generation attempt failed (will retry): {e}")
                    time.sleep(0.3)
                    continue
                else:
                    raise

            # Debug: show raw response when debugging
            if os.environ.get('OMNIS_DEBUG') == '1':
                try:
                    print(f"[DEBUG] raw response: {response}")
                except Exception:
                    pass

            # Try to get text content safely
            try:
                content = getattr(response, 'text', None)
            except Exception:
                content = None

            # If direct text not available, attempt to assemble from candidates -> content -> parts
            if not content or not str(content).strip():
                try:
                    candidates = getattr(response, 'candidates', None) or []
                    for cand in candidates:
                        try:
                            cand_content = getattr(cand, 'content', None)
                            if cand_content and getattr(cand_content, 'parts', None):
                                parts = cand_content.parts
                                text_parts = []
                                for p in parts:
                                    # some parts may be objects with .text
                                    t = getattr(p, 'text', None)
                                    if t:
                                        text_parts.append(t)
                                joined = ''.join(text_parts).strip()
                                if joined:
                                    content = joined
                                    break
                        except Exception:
                            continue
                except Exception:
                    content = None

            if content and str(content).strip():
                break
            # otherwise loop to retry one more time
        
        # Try to get text content safely
        try:
            content = response.text
        except:
            # Response is blocked, check candidates directly
            content = None
            if response.candidates and len(response.candidates) > 0:
                candidate = response.candidates[0]
                if hasattr(candidate, 'content') and candidate.content and len(candidate.content.parts) > 0:
                    try:
                        content = candidate.content.parts[0].text
                    except:
                        pass
        
        if content and str(content).strip():
            return {
                'choices': [{
                    'message': {
                        'content': str(content).strip().replace('*', '').replace('#', '')
                    }
                }]
            }
        else:
            # Handle blocked or empty content with a helpful response
            return {
                'choices': [{
                    'message': {
                        'content': "I'm not sure about that. Please ask me about the school rules, or try rephrasing your question."
                    }
                }]
            }
    except Exception as e:
        print(f"Error getting AI response: {e}")
        error_msg = str(e)
        if "429" in error_msg or "Quota exceeded" in error_msg:
             return {
                'choices': [{
                    'message': {
                        'content': "I'm currently busy with too many requests. Please wait a minute."
                    }
                }]
            }
        
        # Return a helpful error message instead of error
        return {
            'choices': [{
                'message': {
                    'content': "I couldn't process that. Could you please rephrase your question?"
                }
            }]
        }


if __name__ == '__main__':
    result = get_chat_response("tell me about langchain")
    if 'error' not in result:
        print(result['choices'][0]['message']['content'])
    else:
        print(f"Error: {result['error']}")
