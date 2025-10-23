# 🎯 UX Framework Quick Reference

## 🚀 **Quick Start**

### **1. Add to Any Script**
```bash
#!/bin/bash

# Source the UX framework
source "$(dirname "$0")/ux-framework.sh"

# Initialize
init_ux_framework "Your Script" '(
    ["operation1"]=60
    ["operation2"]=120
)'
```

### **2. Replace Basic Commands**
```bash
# Before
echo "Starting..."
docker compose up -d

# After
print_header "Starting Deployment"
execute_with_error_handling "docker compose up -d" "Starting services"
```

### **3. Add Confirmations**
```bash
# Before
docker compose down -v

# After
if ! confirm_action "Remove all containers?"; then
    return 0
fi
execute_with_error_handling "docker compose down -v" "Removing containers"
```

---

## 🛠️ **Essential Functions**

### **Print Functions**
```bash
print_status "Info message"
print_success "Success message"
print_warning "Warning message"
print_error "Error message"
print_header "Section header"
print_progress "Current operation"
print_activity "Background activity"
```

### **User Interaction**
```bash
confirm_action "Continue?"           # Default: No
confirm_action "Continue?" "y"      # Default: Yes
show_time_estimate "operation"
```

### **Error Handling**
```bash
execute_with_error_handling "command" "description"
show_error_details $exit_code "context"
```

### **Background Processes**
```bash
start_background_process "command" "name"
check_background_processes
show_background_status
```

### **Prerequisites**
```bash
check_prerequisites "docker docker-compose nas-mount disk-space"
```

---

## 📋 **Common Patterns**

### **Deployment Script Structure**
```bash
main() {
    print_header "Deployment Script"
    
    # Check prerequisites
    check_prerequisites "docker docker-compose"
    
    # Show summary
    show_deployment_summary "$build" "$clean" "$logs" "$background"
    
    # Confirm
    if ! confirm_action "Proceed?"; then
        return 0
    fi
    
    # Deploy
    show_time_estimate "deploy"
    execute_with_error_handling "docker compose up -d" "Starting services"
    
    # Show results
    print_success "Deployment complete!"
    show_access_info "main-app"
}
```

### **Error Handling Pattern**
```bash
if ! execute_with_error_handling "command" "description"; then
    print_error "Operation failed"
    return 1
fi
```

### **Confirmation Pattern**
```bash
if ! confirm_action "This will delete data. Continue?"; then
    print_status "Operation cancelled"
    return 0
fi
```

### **Background Process Pattern**
```bash
local pid=$(start_background_process "long-running-command" "process-name")
print_activity "Background process started (PID: $pid)"
```

---

## 🎨 **Color Coding**

- **Blue**: Info messages
- **Green**: Success messages
- **Yellow**: Warning messages
- **Red**: Error messages
- **Purple**: Headers
- **Cyan**: Progress updates
- **Bold**: Important messages

---

## ⏱️ **Time Estimates**

```bash
# Common time estimates
["prerequisites"]=30      # 30 seconds
["cleanup"]=60           # 1 minute
["build"]=300            # 5 minutes
["deploy"]=120           # 2 minutes
["health_check"]=30      # 30 seconds
```

---

## 🔧 **Customization**

### **Custom Prerequisites**
```bash
# In ux-framework.sh, add:
case $requirement in
    custom-check)
        if ! your_check; then
            print_error "Custom check failed"
            return 1
        fi
        print_success "Custom check passed"
        ;;
esac
```

### **Custom Access Info**
```bash
# In ux-framework.sh, add:
case $service in
    custom-service)
        echo "  🔧 Custom Service: http://localhost:8080"
        ;;
esac
```

---

## 📊 **Available Prerequisites**

- `docker`: Check if Docker is running
- `docker-compose`: Check if Docker Compose is available
- `nas-mount`: Check if NAS is mounted
- `disk-space`: Check available disk space

---

## 🚀 **Available Services**

- `main-app`: Main application
- `grafana`: Grafana dashboards
- `prometheus`: Prometheus monitoring
- `node-exporter`: Node exporter

---

## 💡 **Tips**

1. **Always use error handling** for important commands
2. **Provide confirmations** for destructive operations
3. **Show time estimates** for long operations
4. **Use appropriate print functions** for different message types
5. **Test thoroughly** after applying the framework

---

## 📝 **Template**

```bash
#!/bin/bash

# Source the UX framework
source "$(dirname "$0")/ux-framework.sh"

# Initialize
init_ux_framework "Your Script" '(
    ["operation"]=60
)'

main() {
    print_header "Your Script"
    
    check_prerequisites "docker"
    
    if ! confirm_action "Proceed?"; then
        return 0
    fi
    
    show_time_estimate "operation"
    execute_with_error_handling "your-command" "description"
    
    print_success "Complete!"
}

main "$@"
```

**Built with ❤️ for the news intelligence community**
