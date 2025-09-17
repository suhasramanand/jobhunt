# Job Hunt

A full-stack job aggregator that automatically scrapes entry-level software engineering positions with visa sponsorship from major job boards and company career sites. The system runs every 2 hours via GitHub Actions and provides a modern React frontend for browsing and filtering job opportunities.

🌐 **Live Demo**: https://suhasramanand.github.io/jobhunt

## 🎯 Features

- **Automated Scraping**: Runs every 2 hours via GitHub Actions
- **Smart Filtering**: Targets new grad/entry-level positions (≤ 2 years experience)
- **Visa Sponsorship Detection**: Automatically identifies jobs offering visa sponsorship
- **Modern Frontend**: React app with Tailwind CSS and shadcn/ui components
- **Real-time Updates**: Frontend fetches latest data from GitHub repo
- **Responsive Design**: Works on desktop and mobile devices
- **Job Categories**: SDE, SWE, DevOps, Cloud, AI/ML roles

## 🏗️ Architecture

```
jobhunt/
├── scraper/                 # Python scraper
│   ├── scrape_jobs.py      # Main scraper script
│   └── requirements.txt    # Python dependencies
├── data/
│   └── jobs.csv           # Job data (auto-updated)
├── frontend/              # React application
│   ├── src/
│   │   ├── App.jsx        # Main React component
│   │   ├── components/    # UI components
│   │   └── lib/          # Utilities
│   └── package.json      # Node.js dependencies
├── .github/workflows/
│   └── scraper.yml       # GitHub Actions workflow
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/suhasramanand/jobhunt.git
cd jobhunt
```

### 2. Set Up the Scraper

```bash
# Navigate to scraper directory
cd scraper

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright browsers
playwright install chromium

# Run scraper locally (optional)
python scrape_jobs.py
```

### 3. Set Up the Frontend

```bash
# Navigate to frontend directory
cd ../frontend

# Install dependencies
npm install

# Start development server
npm start
```

The frontend will be available at `http://localhost:3000`.

## 📊 Data Schema

The scraper saves job data to `data/jobs.csv` with the following schema:

| Column | Description |
|--------|-------------|
| `id` | Unique job identifier |
| `title` | Job title |
| `company` | Company name |
| `location` | Job location |
| `role` | Job category (SDE, SWE, DevOps, Cloud, AI/ML) |
| `post_url` | Link to original job posting |
| `posted_at` | When the job was posted |
| `experience_text` | Experience requirements text |
| `visa_sponsorship` | Boolean indicating visa sponsorship availability |
| `snippet` | Job description snippet |
| `scraped_at` | When this job was scraped |

## 🔧 Configuration

### Scraper Settings

Edit `scraper/scrape_jobs.py` to modify:

- **Target Roles**: Update `TARGET_ROLES` list
- **Experience Filter**: Modify `MAX_EXPERIENCE_YEARS`
- **Time Window**: Change `SCRAPE_WITHIN_HOURS`
- **Visa Keywords**: Update keyword lists for sponsorship detection
- **Job Sources**: Add/modify job board configurations

### GitHub Actions Schedule

Edit `.github/workflows/scraper.yml` to change the scraping frequency:

```yaml
schedule:
  - cron: "0 */2 * * *"  # Every 2 hours
  # - cron: "0 */6 * * *"  # Every 6 hours
  # - cron: "0 0 * * *"    # Daily at midnight
```

## 🎨 Frontend Features

### Filters
- **Search**: Filter by company name or job title
- **Role**: Dropdown filter for job categories
- **Visa Sponsorship**: Toggle to show only jobs with sponsorship

### Job Cards
- Clean, responsive design with hover effects
- Role badges with color coding
- Visa sponsorship indicators
- Direct links to original job postings
- Posted date and scraping timestamp

## 🔄 Automated Workflow

1. **GitHub Actions Trigger**: Runs every 2 hours
2. **Environment Setup**: Installs Python dependencies and Playwright
3. **Job Scraping**: Executes scraper across configured job boards
4. **Data Processing**: Filters jobs by experience and visa sponsorship
5. **Deduplication**: Removes duplicate entries
6. **CSV Update**: Saves results to `data/jobs.csv`
7. **Auto-commit**: Commits and pushes changes to repository

## 🧪 Testing Locally

### Test the Scraper

```bash
cd scraper
python scrape_jobs.py
```

Check the output in `data/jobs.csv` and `scraper.log`.

### Test the Frontend

```bash
cd frontend
npm start
```

The app will fetch data from the GitHub repository's `jobs.csv` file.

### Manual GitHub Actions Trigger

1. Go to your repository on GitHub
2. Navigate to "Actions" tab
3. Select "Job Scraper" workflow
4. Click "Run workflow"

## 📈 Monitoring

### Logs
- Scraper logs are saved to `scraper/scraper.log`
- GitHub Actions logs are available in the Actions tab

### Metrics
- Job count per scraping run
- Success/failure rates
- Processing time per job board

## 🛠️ Customization

### Adding New Job Boards

1. Add configuration to `JOB_BOARDS` in `scrape_jobs.py`
2. Implement a new parser method (e.g., `scrape_new_site()`)
3. Add the parser to `scrape_all_sources()`

### Modifying Filters

Update the filtering logic in:
- `check_experience_requirement()`
- `check_visa_sponsorship()`
- `categorize_role()`

### Frontend Styling

The frontend uses Tailwind CSS. Modify:
- `frontend/src/index.css` for global styles
- `frontend/tailwind.config.js` for theme customization
- Component files for specific styling

## 🚨 Troubleshooting

### Common Issues

**Scraper fails to install Playwright:**
```bash
# Install system dependencies first
sudo apt-get update
sudo apt-get install -y libnss3-dev libatk-bridge2.0-dev libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libxss1 libasound2
```

**Frontend can't fetch data:**
- Ensure the GitHub repository is public
- Check the CSV file path in the fetch URL
- Verify the GitHub Actions workflow completed successfully

**No jobs found:**
- Check the job board selectors haven't changed
- Verify the filtering criteria aren't too restrictive
- Review the scraper logs for errors

### Debug Mode

Enable debug logging in the scraper:

```python
logging.basicConfig(level=logging.DEBUG)
```

## 📝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test locally
5. Submit a pull request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🙏 Acknowledgments

- Built with [Playwright](https://playwright.dev/) for web scraping
- Frontend powered by [React](https://reactjs.org/) and [Tailwind CSS](https://tailwindcss.com/)
- UI components from [shadcn/ui](https://ui.shadcn.com/)
- CSV parsing with [PapaParse](https://www.papaparse.com/)

---

**Note**: This tool is for educational and personal use. Please respect the terms of service of the job boards you're scraping and consider rate limiting your requests.
