# Teams Integration Documentation

This directory contains documentation related to Microsoft Teams integration for the DTCE AI Bot.

## Available Documentation

### Setup and Configuration
- [Teams App Deployment](./teams-deployment.md) - How to deploy the Teams app package
- [Manifest Configuration](./manifest-config.md) - Understanding the Teams app manifest
- [Permissions and Compliance](./permissions.md) - Teams app permissions and compliance requirements

### Development
- [Teams Bot Framework](./bot-framework.md) - Working with the Teams Bot Framework
- [Message Extensions](./message-extensions.md) - Implementing Teams message extensions
- [Adaptive Cards](./adaptive-cards.md) - Creating rich interactive cards

### Testing
- [Local Testing](./local-testing.md) - Testing Teams integration locally
- [Deployment Testing](./deployment-testing.md) - Testing in Teams environments

## Quick Reference

### Current Package Version
- **Version**: 1.2.0
- **Package Location**: `/teams-package/`
- **Manifest**: `/teams-package/manifest.json`

### Key Features
- Document synchronization with SharePoint/OneDrive
- Interactive chat interface
- Real-time document processing
- Compliance and security features

### Supported Teams Features
- Personal chats
- Group chats
- Channel conversations
- Message extensions
- Adaptive cards

## Getting Started

1. Review the [Teams App Deployment guide](./teams-deployment.md)
2. Configure your Teams environment following [Setup documentation](../SETUP.md)
3. Test locally using the [Local Testing guide](./local-testing.md)
4. Deploy using the package in `/teams-package/`

## Package Structure

```
teams-package/
├── manifest.json          # Teams app manifest
├── color.png             # App icon (color)
├── outline.png           # App icon (outline)
└── dtce-ai-bot.zip       # Deployable package
```

For more information, see the main [README](../../README.md) and [Setup Guide](../SETUP.md).
