# Salon Business Dashboard

A Streamlit dashboard for analyzing salon business performance.

## Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/yourrepo.git
cd yourrepo
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure secrets:
   - Copy `.streamlit/secrets.example.toml` to `.streamlit/secrets.toml`
   - Fill in your actual credentials in `.streamlit/secrets.toml`

4. Run the application:
```bash
streamlit run app.py
```

## Configuration

The application requires the following configuration in `.streamlit/secrets.toml`:

- AWS credentials for S3 access
- S3 bucket and prefix configuration
- API keys for additional services

See `.streamlit/secrets.example.toml` for the required format.

## Data Structure

The dashboard expects the following data files in your S3 bucket:
- `merged_sales_data.csv`
- `merged_service_data.csv`

## Features

- MTD Sales Overview
- Outlet Comparison
- Service & Product Analysis
- Growth Analysis

## Data Processing

The dashboard automatically processes and caches data in S3:
- Raw data files are read from S3
- Processed data is saved back to S3
- Subsequent runs will use cached processed data unless the raw data changes

## Security Notes

- Never commit your `.env` file or expose AWS credentials
- Use appropriate IAM roles and policies for S3 access
- Consider using AWS Secrets Manager for production deployments

## Troubleshooting

1. If you see S3 access errors:
   - Verify your AWS credentials are correct
   - Check that your S3 bucket name and region are correct
   - Ensure your AWS user has appropriate S3 permissions

2. If data processing fails:
   - Check the data format in your CSV files
   - Verify all required columns are present
   - Check the S3 bucket permissions

## Support

For issues or questions, please create an issue in the repository. 