# Deploying the RSVP System to Render.com

This guide will walk you through deploying your RSVP system to Render.com.

## Prerequisites

1. A [Render.com account](https://dashboard.render.com/register)
2. Your RSVP system code in a Git repository (GitHub, GitLab, or Bitbucket)

## Deployment Steps

### 1. Create a Render.com Account

Sign up for a Render.com account if you don't already have one.

### 2. Connect Your Repository

1. In the Render dashboard, click on "New" and select "Blueprint"
2. Connect your Git repository (GitHub, GitLab, or Bitbucket)
3. Select the repository containing your RSVP system
4. Render will automatically detect the `render.yaml` file and configure your services

### 3. Configure Environment Variables

While the `render.yaml` file includes most environment variables, you'll need to manually set the following sensitive values:

- `MAIL_PASSWORD`: Your email password
- `TWILIO_ACCOUNT_SID`: Your Twilio Account SID
- `TWILIO_AUTH_TOKEN`: Your Twilio Auth Token
- `TWILIO_PHONE_NUMBER`: Your Twilio Phone Number
- `SUPER_ADMIN_PASS`: Password for the super admin

To set these:
1. After your services are created, go to the "Environment" tab for your web service
2. Add each of these environment variables with their values
3. Click "Save Changes"

### 4. Database Setup

The PostgreSQL database will be automatically created based on the `render.yaml` configuration. The database migration will run automatically as part of the deployment process through the `preDeployCommand` in render.yaml.

If you need to run migrations manually:

1. Go to your web service in the Render dashboard
2. Click on the "Shell" tab
3. Run the database migration script:
   ```
   python render_migrate.py
   ```

### 5. Verify Deployment

1. Once deployment is complete, click on the URL provided by Render to access your application
2. Verify that the Flask application is working by accessing the root URL
3. Test key functionality such as guest management and the RSVP system

## Understanding Your Deployment

Your RSVP system on Render.com consists of:

1. **Flask Web Service**: Runs your Flask application
   - Handles the RSVP system, guest management, and notifications
   - Provides all the core functionality needed for the wedding RSVP process

2. **PostgreSQL Database**: Stores all your wedding, guest, and RSVP data

## Customization Notes

- **Primary color**: The system uses #998103 as the primary color (changed from the original #2c3e50)
- **Email configuration**: Set to use albea.websitewelcome.com on port 465
- **Notification system**: Uses both SMS (via Twilio) and email for guest communications
- **Couple names**: Dynamic couple names are used in email templates

## Troubleshooting

### Application Not Starting

If your application fails to start:
1. Check the logs in the Render dashboard
2. Verify that all environment variables are set correctly
3. Ensure the database migration has been run

### Database Connection Issues

If you encounter database connection problems:
1. Verify the `DATABASE_URL` environment variable is set correctly
2. Check if your IP is allowed in the database's access controls
3. Ensure your database service is running

## Scaling Your Application

The current configuration uses Render's free tier. To scale:
1. Go to your web service in the Render dashboard
2. Click on "Change Plan"
3. Select a higher tier based on your needs

## Additional Resources

- [Render Docs: Python](https://render.com/docs/deploy-python)
- [Render Docs: PostgreSQL](https://render.com/docs/databases)
- [Render Docs: Environment Variables](https://render.com/docs/environment-variables)
