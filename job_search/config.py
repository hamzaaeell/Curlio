"""
Job search configuration — boards, categories, regions, and query templates.
Edit this file to add/remove job boards, roles, or regions.
"""

# ---------------------------------------------------------------------------
# Job boards — site: prefix used in Google queries
# ---------------------------------------------------------------------------
JOB_BOARDS = {
    "GREENHOUSE": "site:boards.greenhouse.io",
    "LEVER":      "site:jobs.lever.co",
    "ASHBY":      "site:jobs.ashbyhq.com",
    "WORKABLE":   "site:workable.com",
}

# ---------------------------------------------------------------------------
# Job categories — each has a list of query keyword groups.
# Multiple groups = multiple searches per board (Google has ~32 OR limit).
# ---------------------------------------------------------------------------
JOB_CATEGORIES = {
    "DEVOPS": [
        [
            "DevOps", "SRE", "Platform Engineer", "Cloud Engineer",
            "Infrastructure Engineer", "Site Reliability Engineer",
        ],
        [
            "Kubernetes", "K8s", "DevSecOps", "Cloud Architect",
        ],
    ],
    "DATA": [
        [
            "Data Engineer", "Analytics Engineer", "ETL Engineer", "Data Platform",
        ],
    ],
    "AI_ML": [
        [
            "AI Engineer", "ML Engineer", "Machine Learning Engineer", "Data Scientist",
        ],
        [
            "LLM Engineer", "MLOps", "NLP Engineer", "Computer Vision",
        ],
    ],
    "BACKEND": [
        [
            "Backend Engineer", "Software Engineer", "Python Developer",
            "Go Developer", "Rust Developer",
        ],
    ],
}

# ---------------------------------------------------------------------------
# Region targeting — appended to every query
# ---------------------------------------------------------------------------
REGION_GROUPS = {
    "INTL": [
        "Europe", "EMEA", "India", "APAC", "LATAM", "UAE", "worldwide", "global",
    ],
    "US": [
        "United States", "USA", "US-based", "nationwide",
    ],
}

# ---------------------------------------------------------------------------
# Region label mapping — maps keywords found in job location to a region tag
# ---------------------------------------------------------------------------
REGION_LABELS = {
    "europe":       ["europe", "emea", "uk", "germany", "france", "netherlands",
                     "spain", "italy", "poland", "sweden", "switzerland", "belgium",
                     "denmark", "norway", "finland", "austria", "portugal", "ireland"],
    "asia_pacific": ["apac", "india", "australia", "singapore", "japan", "korea",
                     "china", "hong kong", "new zealand", "philippines", "indonesia",
                     "malaysia", "thailand", "vietnam"],
    "latin_america":["latam", "latin america", "brazil", "mexico", "argentina",
                     "colombia", "chile", "peru"],
    "middle_east":  ["uae", "dubai", "saudi", "qatar", "bahrain", "kuwait",
                     "middle east", "israel"],
    "north_america":["united states", "usa", "canada", "us-based", "nationwide",
                     "san francisco", "new york", "seattle", "austin", "boston"],
    "worldwide":    ["worldwide", "global", "remote", "anywhere"],
}

# ---------------------------------------------------------------------------
# Skills to extract — scanned from job description text
# ---------------------------------------------------------------------------
SKILL_KEYWORDS = [
    # Cloud
    "AWS", "Azure", "GCP", "Google Cloud Platform", "Cloud",
    # Containers / orchestration
    "Docker", "Kubernetes", "K8s", "Helm", "ArgoCD",
    # IaC
    "Terraform", "Pulumi", "Ansible", "CloudFormation",
    # CI/CD
    "CI/CD", "GitHub Actions", "Jenkins", "GitLab CI",
    # Languages
    "Python", "Go", "Rust", "TypeScript", "Ruby", "Java", "Scala",
    # Data
    "Snowflake", "Airflow", "dbt", "Spark", "Kafka", "S3",
    # ML
    "PyTorch", "TensorFlow", "Fine-tuning", "LLM",
    # Observability
    "Prometheus", "Grafana", "Datadog", "OpenTelemetry",
    # Misc
    "Microservices", "Agile", "OAuth", "EKS", "GKE", "AKS",
]

# ---------------------------------------------------------------------------
# Scraper settings
# ---------------------------------------------------------------------------
RESULTS_PER_SEARCH = 20       # Google results to fetch per query
REQUEST_DELAY_MIN  = 2.0      # Min seconds between job page scrapes
REQUEST_DELAY_MAX  = 5.0      # Max seconds (random jitter)
DB_PATH            = "jobs.db" # SQLite database file
