import time
import json
import urllib.request
import urllib.error

def test_video(url, name):
    print(f"\n==================================================", flush=True)
    print(f"Testing {name}", flush=True)
    print(f"URL: {url}", flush=True)
    print(f"==================================================", flush=True)
    
    start_wall_time = time.time()
    
    # 1. Post request to process endpoint
    req_data = json.dumps({"url": url}).encode("utf-8")
    req = urllib.request.Request(
        "http://127.0.0.1:5000/api/videos/process",
        data=req_data,
        headers={"Content-Type": "application/json"}
    )
    
    try:
        resp = urllib.request.urlopen(req)
        res_data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.read().decode('utf-8')}", flush=True)
        return
    except Exception as e:
        print(f"Initial request failed: {e}", flush=True)
        return
        
    job_id = res_data.get("job_id") or res_data.get("data", {}).get("job_id")
    # If completed synchronously (cache or fast processing)
    if not job_id and res_data.get("success") and res_data.get("data", {}).get("article"):
        print("Completed synchronously (Cache or Instant Execution)!", flush=True)
        data = res_data["data"]
        print(f"Transcript Source: {data.get('transcript_source')}", flush=True)
        print(f"Article Title: {data.get('article', {}).get('title')}", flush=True)
        return
        
    print(f"Job ID: {job_id}", flush=True)
    
    stage_history = []
    last_stage = None
    last_msg = None
    stage_start_time = time.time()
    
    while True:
        status_req = urllib.request.Request(f"http://127.0.0.1:5000/api/jobs/{job_id}")
        try:
            status_resp = urllib.request.urlopen(status_req)
            status_data = json.loads(status_resp.read().decode("utf-8"))
        except Exception as e:
            print(f"Status check failed: {e}", flush=True)
            time.sleep(1)
            continue
            
        job = status_data.get("data", {})
        stage = job.get("stage")
        progress = job.get("progress")
        status = job.get("status")
        msg = job.get("stage_message") or job.get("message")
        
        now = time.time()
        if stage != last_stage or msg != last_msg:
            if stage != last_stage and last_stage is not None:
                duration = now - stage_start_time
                stage_history.append((last_stage, duration))
                print(f"  --> Completed stage [{last_stage}] in {duration:.2f}s", flush=True)
                stage_start_time = now
            print(f"[{now - start_wall_time:.1f}s] Stage: {stage} ({progress}%) - {msg}", flush=True)
            last_stage = stage
            last_msg = msg
            
        if status in ["completed", "failed"]:
            total_duration = now - start_wall_time
            if last_stage:
                stage_history.append((last_stage, now - stage_start_time))
            print("\n--- Pipeline Summary ---", flush=True)
            print(f"Final Status: {status.upper()}", flush=True)
            print(f"Total Duration: {total_duration:.2f}s", flush=True)
            result = job.get("result", {})
            print(f"Transcript Source Used: {result.get('transcript_source', 'N/A')}", flush=True)
            print(f"Article Generated: {'Yes' if result.get('article') else 'No'}", flush=True)
            print("\nStage Breakdown:", flush=True)
            for s_name, s_dur in stage_history:
                print(f"  - {s_name}: {s_dur:.2f}s", flush=True)
            
            if status == "failed":
                err = job.get("error", {})
                print(f"Error Code: {err.get('code')}", flush=True)
                print(f"Error Message: {err.get('message')}", flush=True)
            else:
                art = result.get("article", {})
                content_preview = art.get("content", "")[:150] + "..." if len(art.get("content", "")) > 150 else art.get("content", "")
                print(f"Article Title: {art.get('title')}", flush=True)
                print(f"Content Preview:\n{content_preview}", flush=True)
            break
            
        time.sleep(0.5)

if __name__ == "__main__":
    print("Starting VETRI Scenario Verification...", flush=True)
    
    # 1. Short public YouTube video with captions available
    test_video("https://www.youtube.com/watch?v=jNQXAC9IVRw", "Scenario 1: Short Video with Captions (youtube-transcript-api)")
    
    # 2. Public video where transcript is unavailable (Whisper fallback required)
    test_video("https://www.youtube.com/watch?v=Lw9rCoM4_CU", "Scenario 2: Video without Captions (Whisper Fallback)")
    
    # 3. Longer public video
    test_video("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "Scenario 3: Longer Public Video")
