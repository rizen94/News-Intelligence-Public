# Frontend Debugging Quick Reference
## Cheat Sheet for News Intelligence System

---

## 🚀 Quick Start

### Access Debug Tools (Development Mode)

Open browser console and use:

```javascript
// Debug Helper
window.debugHelper.getDebugInfo()           // Get system info
window.debugHelper.getApiCallStats()        // API statistics
window.debugHelper.checkNetworkStatus()     // Test connection
window.debugHelper.measurePerformance()     // Performance timing

// Feature Testing
featureTestHelper.runAllTests()            // Run all tests
featureTestHelper.runCriticalTests()       // Run critical only
featureTestHelper.getSummary()             // Get results
```

---

## 🔍 Common Debugging Scenarios

### 1. API Not Responding

```javascript
// Check API status
window.debugHelper.checkNetworkStatus()

// Check API call logs
window.debugHelper.getApiCallStats()

// In Network tab:
// - Filter by XHR/Fetch
// - Check status codes
// - Verify CORS headers
// - Check request payload
```

### 2. Component Not Updating

```javascript
// Use React DevTools
// 1. Inspect component props/state
// 2. Check if component re-renders
// 3. Verify context values
// 4. Check for memoization issues

// Or use debug helper
window.debugHelper.logRender('ComponentName', props, state)
```

### 3. Performance Issues

```javascript
// Measure performance
window.debugHelper.measurePerformance('Operation', () => {
  // Your code here
})

// Or use marks
window.debugHelper.startMark('operation')
// ... code ...
window.debugHelper.endMark('operation')

// Check React Profiler
// DevTools → Profiler → Record → Interact → Stop
```

### 4. State Management Issues

```javascript
// Log state changes
window.debugHelper.logStateChange('Component', 'stateName', prev, next)

// Check localStorage
localStorage.getItem('currentDomain')
localStorage.getItem('apiBaseUrl')

// Monitor storage changes (auto-enabled in dev)
// Watch console for storage events
```

### 5. Feature Validation

```javascript
// Run feature tests
featureTestHelper.runAllTests()

// Check results
featureTestHelper.getSummary()

// Export results
featureTestHelper.exportResults()
```

---

## 🛠️ Browser DevTools Shortcuts

### Chrome/Edge
- `F12` - Open DevTools
- `Ctrl+Shift+I` - Open DevTools
- `Ctrl+Shift+J` - Console tab
- `Ctrl+Shift+C` - Element selector
- `Ctrl+R` - Hard refresh
- `Ctrl+Shift+R` - Hard refresh (clear cache)

### Firefox
- `F12` - Open DevTools
- `Ctrl+Shift+K` - Console
- `Ctrl+Shift+C` - Element selector

### Safari
- `Cmd+Option+I` - Open DevTools
- `Cmd+Option+C` - Console

---

## 📊 Network Debugging Checklist

- [ ] Status code is 200 (or expected code)
- [ ] Response time < 500ms
- [ ] Request headers correct
- [ ] Response headers present
- [ ] CORS headers valid
- [ ] Payload size reasonable
- [ ] Error responses structured
- [ ] Retry logic working

---

## 🎯 Feature Testing Checklist

### API Connection
- [ ] Connection indicator shows status
- [ ] Status updates on connection change
- [ ] Manual refresh works
- [ ] Status persists on reload

### Domain Switching
- [ ] Domain selector works
- [ ] URL updates correctly
- [ ] Data refreshes
- [ ] Active domain highlighted

### Data Loading
- [ ] Loading states visible
- [ ] Empty states show
- [ ] Error states display
- [ ] Pagination works
- [ ] Filters apply

### Performance
- [ ] Page loads < 3s
- [ ] Interactions responsive
- [ ] No memory leaks
- [ ] Bundle size reasonable

---

## 🐛 Error Patterns to Watch

### Common Issues

1. **Unhandled Promise Rejections**
   - Check console for red errors
   - Look for "Uncaught (in promise)"

2. **CORS Errors**
   - Check Network tab → Headers
   - Verify Access-Control-Allow-Origin

3. **State Update Warnings**
   - "Cannot update during render"
   - Use useEffect for side effects

4. **Memory Leaks**
   - Check Memory tab
   - Look for detached DOM nodes

5. **Performance Issues**
   - Use Profiler tab
   - Check for slow renders

---

## 📱 Mobile Testing

### Device Mode (Chrome)
1. `Ctrl+Shift+M` - Toggle device toolbar
2. Select device from dropdown
3. Test touch interactions
4. Check viewport size

### Real Device Testing
- Test on actual devices
- Check touch targets (min 44x44px)
- Verify text readability
- Test network conditions

---

## ♿ Accessibility Quick Check

1. **Keyboard Navigation**
   - Tab through all elements
   - Check focus indicators
   - Verify tab order

2. **Screen Reader**
   - Use NVDA/VoiceOver
   - Check alt text
   - Verify ARIA labels

3. **Color Contrast**
   - Use WebAIM checker
   - Minimum 4.5:1 ratio

---

## 🔧 Pro Tips

1. **Use Incognito Mode**
   - Eliminates extension interference
   - Fresh cache

2. **Network Throttling**
   - Test slow connections
   - Verify loading states

3. **Disable Cache**
   - DevTools → Network → Disable cache
   - Always get fresh data

4. **Break on Exceptions**
   - Sources tab → Breakpoints
   - Pause on exceptions

5. **Monitor Performance**
   - Performance tab → Record
   - Identify bottlenecks

---

## 📝 Daily Checklist

Before deploying:
- [ ] No console errors
- [ ] All API calls successful
- [ ] Performance acceptable
- [ ] Cross-browser tested
- [ ] Mobile responsive
- [ ] Accessibility checked
- [ ] Error handling tested

---

## 🆘 Quick Help

### Debug Helper Methods
```javascript
// Performance
debugHelper.measurePerformance(label, fn)
debugHelper.startMark(label)
debugHelper.endMark(label)

// API
debugHelper.logApiCall(url, method, status, duration)
debugHelper.getApiCallStats()
debugHelper.checkNetworkStatus()

// State
debugHelper.logStateChange(component, state, prev, next)
debugHelper.logRender(component, props, state)

// Info
debugHelper.getDebugInfo()
debugHelper.exportDebugInfo()
```

### Feature Test Methods
```javascript
// Run tests
featureTestHelper.runAllTests()
featureTestHelper.runCriticalTests()
featureTestHelper.runTest('testName')

// Results
featureTestHelper.getSummary()
featureTestHelper.exportResults()
featureTestHelper.clearResults()
```

---

**For detailed information, see:** `FRONTEND_DEBUGGING_GUIDE.md`

