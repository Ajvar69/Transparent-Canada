from flask import Flask, render_template, request
import requests
from datetime import datetime
import json
import urllib.parse  # Needed for URL encoding

app = Flask(__name__)

BASE_URL = "https://open.canada.ca/data/en/api/3/action/"
ITEMS_PER_PAGE = 20  # Number of results per page

@app.route("/")
def home():
    try:
        # Get query parameters
        page = int(request.args.get("page", 1))
        search_query = request.args.get("search", "").strip().lower()  # Ensure case-insensitive matching
        
        selected_org = request.args.get("organization", "").strip()
        if selected_org.startswith("{"):  # Prevent dictionaries from being sent
            print("❌ ERROR: Received invalid organization format")
            selected_org = ""

        sort_order = request.args.get("sort", "none")  # Default: No sorting

        dataset_details = []
        total_items = 0
        all_organizations = {}  # Store organizations as {API_ID: Display_Name}

        # ✅ **Separate Keyword vs. Non-Keyword Searches**
        if search_query:
            # ✅ **Keyword Search (Fetch 1000 results and filter manually)**
            api_url = f"{BASE_URL}package_search?rows=1000&q={urllib.parse.quote(search_query)}"

            if selected_org and selected_org != "All Organizations":
                api_url += f"&fq=organization:{urllib.parse.quote(selected_org)}"

            print(f"🔍 DEBUG: Fetching keyword search data -> {api_url}")

            try:
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                response_json = response.json()
            except requests.exceptions.RequestException as e:
                print(f"\n❌ API request failed: {e}")
                return f"API request failed: {e}"

            dataset_list = response_json.get("result", {}).get("results", [])
            total_items = response_json.get("result", {}).get("count", 0)

            # ✅ **Collect all organizations from the keyword search results**
            filtered_datasets = []
            for dataset in dataset_list:
                title = dataset.get("title", "N/A")
                org_name = dataset.get("organization", {}).get("name", "N/A")  # API ID
                org_title = dataset.get("organization", {}).get("title", "N/A")  # Display name

                all_organizations[org_name] = org_title  # Store API ID & Display Name

                if search_query and search_query not in title.lower():
                    continue  # Skip irrelevant results

                filtered_datasets.append({
                    "title": title,
                    "organization": org_title,
                    "org_api_name": org_name,
                    "last_modified": dataset.get("metadata_modified", "1970-01-01T00:00:00"),
                    "url": dataset["resources"][0]["url"] if dataset.get("resources") else "#"
                })

            # ✅ **Sort the results based on the selected sorting order**
            if sort_order == "newest":
                filtered_datasets.sort(key=lambda x: datetime.strptime(x["last_modified"], "%Y-%m-%dT%H:%M:%S.%f"), reverse=True)
            elif sort_order == "oldest":
                filtered_datasets.sort(key=lambda x: datetime.strptime(x["last_modified"], "%Y-%m-%dT%H:%M:%S.%f"), reverse=False)

            # ✅ **Apply correct pagination AFTER sorting**
            total_items = len(filtered_datasets)
            total_pages = max((total_items // ITEMS_PER_PAGE) + (1 if total_items % ITEMS_PER_PAGE > 0 else 0), 1)

            start_idx = (page - 1) * ITEMS_PER_PAGE
            end_idx = start_idx + ITEMS_PER_PAGE
            dataset_details = filtered_datasets[start_idx:end_idx]

        else:
            # ✅ **Non-Keyword Search: Collect organizations dynamically from dataset search results**
            api_start = (page - 1) * ITEMS_PER_PAGE
            api_url = f"{BASE_URL}package_search?start={api_start}&rows={ITEMS_PER_PAGE}"

            if selected_org and selected_org != "All Organizations":
                api_url += f"&fq=organization:{urllib.parse.quote(selected_org)}"

            # ✅ **Apply sorting directly in API call**
            if sort_order == "newest":
                api_url += "&sort=metadata_modified desc"
            elif sort_order == "oldest":
                api_url += "&sort=metadata_modified asc"

            print(f"🔍 DEBUG: Fetching non-keyword search data -> {api_url}")

            try:
                response = requests.get(api_url, timeout=10)
                response.raise_for_status()
                response_json = response.json()
            except requests.exceptions.RequestException as e:
                print(f"\n❌ API request failed: {e}")
                return f"API request failed: {e}"

            dataset_list = response_json.get("result", {}).get("results", [])
            total_items = response_json.get("result", {}).get("count", 0)

            dataset_details = []
            for dataset in dataset_list:
                org_name = dataset.get("organization", {}).get("name", "N/A")  # API ID
                org_title = dataset.get("organization", {}).get("title", "N/A")  # Display name

                # ✅ **Only store organizations that actually have datasets**
                all_organizations[org_name] = org_title  

                dataset_details.append({
                    "title": dataset.get("title", "N/A"),
                    "organization": org_title,
                    "org_api_name": org_name,
                    "last_modified": dataset.get("metadata_modified", "1970-01-01T00:00:00"),
                    "url": dataset["resources"][0]["url"] if dataset.get("resources") else "#"
                })

            # ✅ **Apply API-provided pagination count**
            total_pages = max((total_items // ITEMS_PER_PAGE) + (1 if total_items % ITEMS_PER_PAGE > 0 else 0), 1)

        # ✅ **Sort organizations for dropdown**
        sorted_organizations = [{"id": key, "name": value} for key, value in sorted(all_organizations.items(), key=lambda x: x[1])]
        sorted_organizations.insert(0, {"id": "", "name": "All Organizations"})

        return render_template(
            "index.html",
            data=dataset_details,
            page=page,
            total_pages=total_pages,
            organizations=sorted_organizations,
            selected_org=selected_org,
            search_query=search_query,
            sort_order=sort_order
        )

    except Exception as e:
        return f"Error fetching data: {e}"

if __name__ == "__main__":
    app.run(debug=True)
