# 🎯 UX Framework Application Guide

## 📋 **Overview**

The UX Framework is a **flexible, reusable system** designed to enhance any deployment script with professional user experience features. It's completely **agnostic** and can be applied to any script without modifying the core functionality.

---

## 🏗️ **Architecture**

### **Modular Design**
- **`ux-framework.sh`**: Core UX functions and utilities
- **`deploy-template.sh`**: Template showing how to apply the framework
- **`deploy-unified.sh`**: Example implementation using the framework
- **`manage-background.sh`**: Background process management
- **`deployment-dashboard.sh`**: Real-time monitoring dashboard

### **Separation of Concerns**
- **Core Logic**: Your deployment logic remains unchanged
- **UX Layer**: Framework provides user experience enhancements
- **Configuration**: Easy to customize for different deployments
- **Reusability**: Apply to any script with minimal changes

---

## 🚀 **How to Apply the Framework**

### **Step 1: Source the Framework**
```bash
#!/bin/bash

# Source the UX framework
source "$(dirname "$0")/ux-framework.sh"

# Initialize the framework
init_ux_framework "Your Script Name" '(
    ["prerequisites"]=30
    ["cleanup"]=60
    ["build"]=300
    ["deploy"]=120
    ["health_check"]=30
)'
```

### **Step 2: Replace Basic Commands**
```bash
# Before (basic)
echo "Starting deployment..."
docker compose up -d

# After (enhanced)
print_header "Starting Deployment"
print_progress "Starting services..."
execute_with_error_handling "docker compose up -d" "Starting services"
```

### **Step 3: Add User Confirmations**
```bash
# Before (basic)
docker compose down -v

# After (enhanced)
if ! confirm_action "This will remove all containers and volumes. Continue?"; then
    print_status "Operation cancelled by user"
    return 0
fi
execute_with_error_handling "docker compose down -v" "Removing containers and volumes"
```

### **Step 4: Add Time Estimates**
```bash
# Before (basic)
docker compose build

# After (enhanced)
show_time_estimate "build"
print_warning "Container rebuild may take 5-10 minutes"
if ! confirm_action "Continue with rebuild?"; then
    return 0
fi
execute_with_error_handling "docker compose build" "Building containers"
```

---

## 🛠️ **Framework Functions**

### **Print Functions**
```bash
print_status "General information"
print_success "Operation completed successfully"
print_warning "Potential issue detected"
print_error "Error occurred"
print_header "Section header"
print_progress "Current operation"
print_estimate "Time estimate"
print_confirmation "User confirmation needed"
print_activity "Background activity"
```

### **User Interaction**
```bash
# Confirm action with default "no"
confirm_action "This will delete all data. Continue?"

# Confirm action with default "yes"
confirm_action "Continue with deployment?" "y"

# Show time estimate
show_time_estimate "build"

# Show progress with spinner
show_progress $pid "Building containers"
```

### **Error Handling**
```bash
# Execute command with error handling
execute_with_error_handling "docker compose up -d" "Starting services"

# Show detailed error information
show_error_details $exit_code "Starting services"
```

### **Background Processes**
```bash
# Start background process
local pid=$(start_background_process "docker compose logs -f" "logs")

# Check background processes
check_background_processes

# Show background status
show_background_status
```

### **Prerequisites Checking**
```bash
# Check multiple prerequisites
check_prerequisites "docker docker-compose nas-mount disk-space"

# Available checks:
# - docker: Check if Docker is running
# - docker-compose: Check if Docker Compose is available
# - nas-mount: Check if NAS is mounted
# - disk-space: Check available disk space
```

---

## 📝 **Example: Converting a Basic Script**

### **Before (Basic Script)**
```bash
#!/bin/bash

echo "Starting deployment..."
docker compose up -d
echo "Deployment complete!"
```

### **After (Enhanced with Framework)**
```bash
#!/bin/bash

# Source the UX framework
source "$(dirname "$0")/ux-framework.sh"

# Initialize the framework
init_ux_framework "My Deployment" '(
    ["deploy"]=120
)'

# Main function
main() {
    print_header "My Deployment Script"
    
    # Check prerequisites
    check_prerequisites "docker docker-compose"
    
    # Show deployment summary
    show_deployment_summary "false" "false" "false" "false"
    
    # Confirm deployment
    if ! confirm_action "Proceed with deployment?"; then
        print_status "Deployment cancelled by user"
        return 0
    fi
    
    # Deploy with error handling
    show_time_estimate "deploy"
    execute_with_error_handling "docker compose up -d" "Starting services"
    
    print_success "Deployment complete!"
    show_access_info "main-app"
}

# Run main function
main "$@"
```

---

## 🔧 **Customization Options**

### **Time Estimates**
```bash
# Customize time estimates for your operations
ESTIMATED_TIMES=(
    ["prerequisites"]=30
    ["cleanup"]=60
    ["build"]=300
    ["deploy"]=120
    ["health_check"]=30
    ["custom_operation"]=180
)
```

### **Prerequisites**
```bash
# Add custom prerequisite checks
check_prerequisites "docker docker-compose custom-check"

# In ux-framework.sh, add your custom check:
case $requirement in
    custom-check)
        # Your custom check logic
        if ! your_custom_check; then
            print_error "Custom check failed"
            return 1
        fi
        print_success "Custom check passed"
        ;;
esac
```

### **Access Information**
```bash
# Customize access information
show_access_info "main-app custom-service"

# Add your custom service:
case $service in
    custom-service)
        echo "  🔧 Custom Service:      http://localhost:8080"
        ;;
esac
```

---

## 📊 **Benefits of the Framework**

### **For Development**
- **Consistent UX**: All scripts have the same professional interface
- **Easy Maintenance**: Update UX features in one place
- **Rapid Development**: Apply framework to new scripts quickly
- **Error Handling**: Built-in error handling and recovery

### **For Users**
- **Clear Feedback**: Always know what's happening
- **Time Estimates**: Know how long operations will take
- **Error Recovery**: Clear guidance on fixing issues
- **Background Support**: Continue working during deployments

### **For Maintenance**
- **Modular Updates**: Update UX features without touching core logic
- **Version Control**: Track UX improvements separately
- **Testing**: Test UX features independently
- **Documentation**: Self-documenting through consistent interface

---

## 🚀 **Migration Strategy**

### **Phase 1: Apply to New Scripts**
1. Use `deploy-template.sh` as starting point
2. Customize for your specific needs
3. Test with framework features

### **Phase 2: Migrate Existing Scripts**
1. Add framework source and initialization
2. Replace basic commands with framework functions
3. Add user confirmations and error handling
4. Test thoroughly

### **Phase 3: Enhance with Advanced Features**
1. Add background process support
2. Implement real-time monitoring
3. Add custom prerequisite checks
4. Create deployment dashboards

---

## 📋 **Best Practices**

### **1. Always Use Error Handling**
```bash
# Good
execute_with_error_handling "docker compose up -d" "Starting services"

# Avoid
docker compose up -d
```

### **2. Provide User Confirmations**
```bash
# Good
if ! confirm_action "This will delete all data. Continue?"; then
    return 0
fi

# Avoid
rm -rf /important/data
```

### **3. Show Time Estimates**
```bash
# Good
show_time_estimate "build"
print_warning "This may take 5-10 minutes"

# Avoid
docker compose build
```

### **4. Use Appropriate Print Functions**
```bash
# Good
print_success "Operation completed"
print_warning "Potential issue"
print_error "Operation failed"

# Avoid
echo "Operation completed"
echo "Potential issue"
echo "Operation failed"
```

---

## 🎯 **Conclusion**

The UX Framework provides a **flexible, reusable system** for enhancing any deployment script with professional user experience features. It's designed to be:

- **Agnostic**: Works with any script
- **Modular**: Easy to customize and extend
- **Maintainable**: Update UX features in one place
- **Professional**: Enterprise-grade user experience

By applying this framework, you can ensure consistent, professional user experience across all your deployment scripts while maintaining the flexibility to customize for specific needs.

**Built with ❤️ for the news intelligence community**
