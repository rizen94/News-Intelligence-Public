# News Intelligence System v4.0 - Frontend Update Plan

## Date: 2025-01-XX
## Status: 📋 **PLANNING**

---

## 🎯 **Overview**

Transform the frontend to support multi-domain navigation with unique views for each major segment (Politics, Finance, Science & Technology). The frontend should provide a newspaper-style experience where users can navigate between domains and see domain-specific content.

---

## 🔍 **Current State Analysis**

### **What's Already Working**
✅ **Domain Context** - `DomainContext` and `DomainSelector` components exist  
✅ **API Integration** - All API calls already include domain parameter  
✅ **Domain Persistence** - Domain selection persists in localStorage  
✅ **Domain Badge** - Navigation shows current domain

### **What Needs to Change**
❌ **URL Routing** - Routes don't include domain (e.g., `/articles` vs `/politics/articles`)  
❌ **Domain-Specific Views** - No unique layouts/features per domain  
❌ **Finance Features** - No finance-specific pages/components  
❌ **Navigation Structure** - Flat navigation, not domain-organized  
❌ **Route Protection** - No domain validation in routes

---

## 🏗️ **Architecture Changes**

### **1. URL Structure**

#### **Current Structure** (v3.0)
```
/articles
/storylines
/topics
/rss-feeds
```

#### **New Structure** (v4.0)
```
/{domain}/articles
/{domain}/storylines
/{domain}/topics
/{domain}/rss-feeds

Examples:
/politics/articles
/finance/articles
/science-tech/articles
```

#### **Domain-Agnostic Routes** (Shared)
```
/dashboard          # Cross-domain overview
/settings           # User settings
/monitoring         # System monitoring
```

---

### **2. Routing Strategy**

#### **Option A: Domain in Path** (Recommended)
- **Pros**: Clear URL structure, bookmarkable, SEO-friendly, explicit domain context
- **Cons**: Requires route updates, redirects for old URLs
- **Implementation**: 
  ```tsx
  <Route path="/:domain/articles" element={<Articles />} />
  <Route path="/:domain/storylines" element={<Storylines />} />
  ```

#### **Option B: Domain in Query/Context Only**
- **Pros**: Minimal route changes, backward compatible
- **Cons**: URLs don't reflect domain, harder to bookmark/share
- **Implementation**: Keep current routes, use context only

**Recommendation**: **Option A** - Better UX, clearer architecture

---

### **3. Component Structure**

```
src/
├── domains/
│   ├── Politics/
│   │   ├── Articles/
│   │   │   ├── PoliticsArticles.tsx
│   │   │   └── PoliticsArticleDetail.tsx
│   │   ├── Storylines/
│   │   │   └── PoliticsStorylines.tsx
│   │   └── Topics/
│   │       └── PoliticsTopics.tsx
│   ├── Finance/
│   │   ├── Articles/
│   │   │   ├── FinanceArticles.tsx
│   │   │   └── FinanceArticleDetail.tsx
│   │   ├── MarketResearch/
│   │   │   ├── MarketResearch.tsx
│   │   │   ├── CorporateAnnouncements.tsx
│   │   │   └── MarketPatterns.tsx
│   │   ├── Storylines/
│   │   │   └── FinanceStorylines.tsx
│   │   └── Topics/
│   │       └── FinanceTopics.tsx
│   └── ScienceTech/
│       ├── Articles/
│       │   └── ScienceTechArticles.tsx
│       ├── Storylines/
│       │   └── ScienceTechStorylines.tsx
│       └── Topics/
│           └── ScienceTechTopics.tsx
├── shared/
│   ├── components/
│   │   ├── DomainLayout/
│   │   │   ├── DomainLayout.tsx
│   │   │   └── DomainBreadcrumb.tsx
│   │   ├── DomainNavigation/
│   │   │   └── DomainNavigation.tsx
│   │   └── DomainRouteGuard/
│   │       └── DomainRouteGuard.tsx
│   └── hooks/
│       ├── useDomainRoute.ts
│       └── useDomainNavigation.ts
```

---

## 📋 **Implementation Plan**

### **Phase 1: Routing Infrastructure**

#### **Step 1.1: Update App.tsx Routing**
```tsx
// App.tsx
<Routes>
  {/* Domain-agnostic routes */}
  <Route path="/" element={<Navigate to="/politics/dashboard" replace />} />
  <Route path="/dashboard" element={<Dashboard />} />
  <Route path="/settings" element={<Settings />} />
  <Route path="/monitoring" element={<Monitoring />} />
  
  {/* Domain-specific routes */}
  <Route path="/:domain/*" element={<DomainLayout />} />
</Routes>
```

#### **Step 1.2: Create DomainLayout Component**
```tsx
// components/shared/DomainLayout/DomainLayout.tsx
const DomainLayout = () => {
  const { domain } = useParams<{ domain: string }>();
  const { setDomain } = useDomain();
  
  // Validate domain and update context
  useEffect(() => {
    if (domain && isValidDomain(domain)) {
      setDomain(domain);
    } else {
      navigate('/politics/dashboard');
    }
  }, [domain]);
  
  return (
    <Routes>
      <Route path="dashboard" element={<Dashboard />} />
      <Route path="articles" element={<Articles />} />
      <Route path="articles/:id" element={<ArticleDetail />} />
      <Route path="storylines" element={<Storylines />} />
      <Route path="storylines/:id" element={<StorylineDetail />} />
      <Route path="topics" element={<Topics />} />
      <Route path="topics/:topicName" element={<TopicArticles />} />
      <Route path="rss-feeds" element={<RSSFeeds />} />
      
      {/* Finance-specific routes */}
      {domain === 'finance' && (
        <>
          <Route path="market-research" element={<MarketResearch />} />
          <Route path="corporate-announcements" element={<CorporateAnnouncements />} />
          <Route path="market-patterns" element={<MarketPatterns />} />
        </>
      )}
    </Routes>
  );
};
```

#### **Step 1.3: Create Domain Route Guard**
```tsx
// components/shared/DomainRouteGuard/DomainRouteGuard.tsx
const DomainRouteGuard = ({ children }: { children: ReactNode }) => {
  const { domain } = useParams<{ domain: string }>();
  const navigate = useNavigate();
  
  useEffect(() => {
    if (!domain || !isValidDomain(domain)) {
      navigate('/politics/dashboard', { replace: true });
    }
  }, [domain, navigate]);
  
  if (!domain || !isValidDomain(domain)) {
    return <Navigate to="/politics/dashboard" replace />;
  }
  
  return <>{children}</>;
};
```

---

### **Phase 2: Navigation Updates**

#### **Step 2.1: Update Navigation Component**
```tsx
// components/Navigation/Navigation.tsx
const Navigation = () => {
  const { domain } = useDomain();
  const location = useLocation();
  
  const navItems = [
    { path: `/${domain}/dashboard`, label: 'Dashboard', icon: '📊' },
    { path: `/${domain}/articles`, label: 'Articles', icon: '📰' },
    { path: `/${domain}/storylines`, label: 'Storylines', icon: '📚' },
    { path: `/${domain}/topics`, label: 'Topics', icon: '🏷️' },
    { path: `/${domain}/rss-feeds`, label: 'RSS Feeds', icon: '📡' },
  ];
  
  // Add finance-specific items
  if (domain === 'finance') {
    navItems.push(
      { path: `/${domain}/market-research`, label: 'Market Research', icon: '📈' },
      { path: `/${domain}/corporate-announcements`, label: 'Corporate News', icon: '🏢' },
      { path: `/${domain}/market-patterns`, label: 'Market Patterns', icon: '📊' }
    );
  }
  
  return (
    <nav>
      <DomainSelector />
      <ul>
        {navItems.map(item => (
          <li key={item.path}>
            <Link to={item.path}>{item.label}</Link>
          </li>
        ))}
      </ul>
    </nav>
  );
};
```

#### **Step 2.2: Update DomainSelector to Navigate**
```tsx
// components/DomainSelector/DomainSelector.tsx
const DomainSelector = () => {
  const { domain, setDomain } = useDomain();
  const navigate = useNavigate();
  const location = useLocation();
  
  const handleDomainChange = (newDomain: string) => {
    setDomain(newDomain);
    
    // Extract current path without domain
    const pathWithoutDomain = location.pathname.replace(`/${domain}`, '');
    
    // Navigate to same path in new domain
    navigate(`/${newDomain}${pathWithoutDomain || '/dashboard'}`);
  };
  
  // ... rest of component
};
```

---

### **Phase 3: Domain-Specific Views**

#### **Step 3.1: Create Base Domain Components**

**Articles Component** (Domain-Aware)
```tsx
// pages/Articles/Articles.tsx
const Articles = () => {
  const { domain } = useParams<{ domain: string }>();
  const { domain: contextDomain } = useDomain();
  const effectiveDomain = domain || contextDomain;
  
  // Use domain-specific API calls
  const { data, loading } = useQuery(
    ['articles', effectiveDomain],
    () => apiService.getArticles({}, effectiveDomain)
  );
  
  // Domain-specific rendering
  if (effectiveDomain === 'finance') {
    return <FinanceArticlesView data={data} />;
  }
  
  return <StandardArticlesView data={data} />;
};
```

#### **Step 3.2: Finance-Specific Components**

**Market Research Page**
```tsx
// domains/Finance/MarketResearch/MarketResearch.tsx
const MarketResearch = () => {
  const { domain } = useDomain();
  
  return (
    <div className="market-research">
      <h1>Market Research</h1>
      <MarketTrendsChart />
      <SectorAnalysis />
      <CompanyPerformance />
    </div>
  );
};
```

**Corporate Announcements Page**
```tsx
// domains/Finance/CorporateAnnouncements/CorporateAnnouncements.tsx
const CorporateAnnouncements = () => {
  const { domain } = useDomain();
  
  const { data } = useQuery(
    ['corporate-announcements', domain],
    () => apiService.getCorporateAnnouncements({}, domain)
  );
  
  return (
    <div className="corporate-announcements">
      <h1>Corporate Announcements</h1>
      <AnnouncementFilters />
      <AnnouncementList announcements={data} />
      <EarningsCalendar />
    </div>
  );
};
```

**Market Patterns Page**
```tsx
// domains/Finance/MarketPatterns/MarketPatterns.tsx
const MarketPatterns = () => {
  const { domain } = useDomain();
  
  const { data } = useQuery(
    ['market-patterns', domain],
    () => apiService.getMarketPatterns({}, domain)
  );
  
  return (
    <div className="market-patterns">
      <h1>Market Pattern Analysis</h1>
      <PatternDetectionChart />
      <CorrelationMatrix />
      <TrendAnalysis />
    </div>
  );
};
```

---

### **Phase 4: Shared Utilities**

#### **Step 4.1: Create Domain Navigation Hook**
```tsx
// hooks/useDomainNavigation.ts
export const useDomainNavigation = () => {
  const { domain } = useDomain();
  const navigate = useNavigate();
  
  const navigateToDomain = (path: string, targetDomain?: string) => {
    const effectiveDomain = targetDomain || domain;
    navigate(`/${effectiveDomain}${path}`);
  };
  
  const switchDomain = (newDomain: string, preservePath: boolean = true) => {
    const currentPath = window.location.pathname;
    const pathWithoutDomain = currentPath.replace(`/${domain}`, '');
    navigate(`/${newDomain}${preservePath ? pathWithoutDomain : '/dashboard'}`);
  };
  
  return { navigateToDomain, switchDomain };
};
```

#### **Step 4.2: Create Domain Route Helper**
```tsx
// hooks/useDomainRoute.ts
export const useDomainRoute = () => {
  const { domain } = useDomain();
  const { pathname } = useLocation();
  
  const getDomainPath = (path: string) => {
    return `/${domain}${path}`;
  };
  
  const getCurrentPathWithoutDomain = () => {
    return pathname.replace(`/${domain}`, '') || '/dashboard';
  };
  
  return { getDomainPath, getCurrentPathWithoutDomain };
};
```

---

### **Phase 5: Finance API Integration**

#### **Step 5.1: Add Finance API Methods**
```tsx
// services/apiService.ts
export const apiService = {
  // ... existing methods
  
  // Finance-specific methods
  getCorporateAnnouncements: async (params: any = {}, domain?: string) => {
    const domainKey = domain || getCurrentDomain();
    const response = await api.get(
      `/api/v4/${domainKey}/finance/corporate-announcements`,
      { params }
    );
    return response.data;
  },
  
  getMarketPatterns: async (params: any = {}, domain?: string) => {
    const domainKey = domain || getCurrentDomain();
    const response = await api.get(
      `/api/v4/${domainKey}/finance/market-patterns`,
      { params }
    );
    return response.data;
  },
  
  getFinancialIndicators: async (params: any = {}, domain?: string) => {
    const domainKey = domain || getCurrentDomain();
    const response = await api.get(
      `/api/v4/${domainKey}/finance/indicators`,
      { params }
    );
    return response.data;
  },
};
```

---

## 🎨 **UI/UX Design Considerations**

### **1. Domain-Specific Branding**
- **Politics**: Blue/red color scheme, political icons
- **Finance**: Green/gold color scheme, financial charts/icons
- **Science & Tech**: Purple/blue color scheme, tech/science icons

### **2. Domain-Specific Layouts**
- **Politics**: Standard article list, timeline view
- **Finance**: Dashboard-style with charts, market data widgets
- **Science & Tech**: Research-focused, paper-style layout

### **3. Navigation Patterns**
- **Top-level**: Domain selector (tabs/chips)
- **Sidebar**: Domain-specific navigation items
- **Breadcrumbs**: Show domain context (e.g., "Finance > Market Research")

---

## 📊 **Migration Strategy**

### **Step 1: Backward Compatibility**
- Keep old routes working with redirects
- `/articles` → `/politics/articles`
- `/storylines` → `/politics/storylines`

### **Step 2: Gradual Migration**
1. Add new domain routes alongside old routes
2. Update navigation to use new routes
3. Add redirects for old routes
4. Remove old routes after testing

### **Step 3: Testing**
- Test domain switching
- Test bookmarking domain-specific URLs
- Test browser back/forward navigation
- Test direct URL access

---

## ✅ **Implementation Checklist**

### **Routing & Navigation**
- [ ] Update `App.tsx` with domain routes
- [ ] Create `DomainLayout` component
- [ ] Create `DomainRouteGuard` component
- [ ] Update `Navigation` component for domain-aware paths
- [ ] Update `DomainSelector` to navigate on change
- [ ] Add redirects for old routes

### **Domain-Specific Views**
- [ ] Create domain-aware `Articles` component
- [ ] Create domain-aware `Storylines` component
- [ ] Create domain-aware `Topics` component
- [ ] Create domain-aware `RSSFeeds` component

### **Finance Features**
- [ ] Create `MarketResearch` page
- [ ] Create `CorporateAnnouncements` page
- [ ] Create `MarketPatterns` page
- [ ] Add finance API methods to `apiService`
- [ ] Create finance-specific components

### **Utilities & Hooks**
- [ ] Create `useDomainNavigation` hook
- [ ] Create `useDomainRoute` hook
- [ ] Update existing components to use domain routes

### **Testing & Polish**
- [ ] Test domain switching
- [ ] Test URL bookmarking
- [ ] Test browser navigation
- [ ] Add loading states
- [ ] Add error handling
- [ ] Update documentation

---

## 🚀 **Next Steps**

1. **Review and Approve Plan** - Confirm approach
2. **Create DomainLayout Component** - Start with routing infrastructure
3. **Update Navigation** - Make navigation domain-aware
4. **Create Finance Pages** - Build finance-specific features
5. **Test and Iterate** - Ensure smooth domain switching

---

*Frontend Update Plan Date: 2025-01-XX*  
*Target Completion: Q1 2026*
