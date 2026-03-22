# Product Requirements Document: OnsenBook — Onsen Ryokan Booking Platform

## 1. Product Overview

OnsenBook is a web-based accommodation booking platform exclusively focused on Japanese onsen ryokan (hot spring inns). It combines onsen-specialized search and filtering, multilingual cultural bridge content, editorial curation across all price ranges, and community-driven discovery features. The platform targets international travelers seeking authentic onsen experiences and domestic Japanese travelers wanting curated onsen getaways.

### 1.1 Vision Statement

Become the global authority for onsen ryokan discovery and booking — the platform travelers trust when they want more than a hotel room, they want an onsen experience.

### 1.2 Success Metrics (Year 1)

- 500–1,000 bookings/month by month 12
- 30+ ryokan partnerships at launch
- 10,000 monthly organic visitors within 6 months
- 4.5+ average user satisfaction rating
- 5 supported languages: JP, EN, CN-S, CN-T, KR

---

## 2. Functional Requirements

### 2.1 Search & Discovery

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| S-01 | Users can search ryokan by destination name, region, or prefecture with autocomplete suggestions | Must |
| S-02 | Users can filter results by onsen water type (sulfur, sodium chloride, alkaline simple, iron, carbon dioxide, hydrogen carbonate, sulfate, radium) | Must |
| S-03 | Users can filter results by bath style (outdoor rotenburo, indoor, cave, riverside, rooftop, sand bath) | Must |
| S-04 | Users can filter results by privacy level (shared public, gender-separated, private rental, in-room private bath) | Must |
| S-05 | Users can filter by price range per person per night (in their local currency) | Must |
| S-06 | Users can filter by meal plan (no meals, breakfast only, half-board with kaiseki, full-board) | Must |
| S-07 | Users can filter by check-in/check-out dates and guest count (adults + children) | Must |
| S-08 | Users can sort results by price (low-high, high-low), rating, distance, or editorial pick score | Must |
| S-09 | Search results display on an interactive map alongside the list view | Should |
| S-10 | Users can filter by therapeutic benefit (skin beautifying, muscle relaxation, joint pain, respiratory) | Should |
| S-11 | Users can filter by tattoo policy (tattoo-friendly, private bath available, cover required, no tattoos) | Should |
| S-12 | Users can filter by accessibility features (wheelchair access, barrier-free baths, elevator) | Should |
| S-13 | Users can save search filters as presets for repeated use | Could |
| S-14 | AI-powered natural language search (e.g., "romantic ryokan with snow view bath near Tokyo under ¥30,000") | Won't (v1) |

### 2.2 Ryokan Listing & Detail

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| L-01 | Each ryokan has a detail page with photo gallery, description, onsen details, room types, and pricing | Must |
| L-02 | Onsen details section shows water type, temperature, source (natural/heated), pH level, bath styles available, and operating hours | Must |
| L-03 | Room types display tatami size (in jo), futon/bed configuration, max occupancy, view type, and whether in-room private bath is included | Must |
| L-04 | Meal plan details show kaiseki course descriptions with seasonal menu examples and dietary accommodation options | Must |
| L-05 | Photo gallery includes categorized photos: rooms, baths (outdoor/indoor), meals, exterior, common areas | Must |
| L-06 | Each listing displays user ratings (overall + subcategories: onsen quality, hospitality, meals, atmosphere, cleanliness) | Must |
| L-07 | Check-in/check-out times, cancellation policy, and house rules are clearly displayed | Must |
| L-08 | Interactive map shows ryokan location with nearby attractions, transit access, and other onsen in the area | Should |
| L-09 | 360-degree virtual tour of bath facilities | Could |
| L-10 | Real-time availability calendar showing open dates for each room type | Should |
| L-11 | "Compare" feature allowing side-by-side comparison of up to 3 ryokan on onsen-specific attributes | Could |
| L-12 | Seasonal highlight banners showing current seasonal experience (autumn foliage, snow bath, cherry blossom) | Should |

### 2.3 Booking Flow

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| B-01 | Users can select room type, dates, guest count, and meal plan to create a reservation | Must |
| B-02 | Pricing displays per-person-per-night in user's local currency with JPY equivalent shown | Must |
| B-03 | Booking form collects guest names, contact info, arrival time, dietary restrictions, and special requests | Must |
| B-04 | Payment processing via Stripe with support for major credit cards, Apple Pay, and Google Pay | Must |
| B-05 | Booking confirmation sent via email with reservation details, access directions, and onsen etiquette quick guide | Must |
| B-06 | Users can view, modify, and cancel bookings from their dashboard according to the cancellation policy | Must |
| B-07 | Add-on experience booking (private onsen session, sake tasting, cooking class) during reservation flow | Could |
| B-08 | Split payment between multiple guests | Won't (v1) |
| B-09 | Gift certificate purchase for ryokan stays | Won't (v1) |

### 2.4 User Accounts & Profiles

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| U-01 | Users can register and log in via email/password or social login (Google, LINE) | Must |
| U-02 | User profile stores name, preferred language, currency, travel preferences, and booking history | Must |
| U-03 | Users can save/favorite ryokan to a wishlist | Must |
| U-04 | Users can write reviews for ryokan they have stayed at (verified booking required) | Must |
| U-05 | Users can view their booking history and upcoming reservations on a dashboard | Must |
| U-06 | Hot Spring Passport: gamification system tracking visited onsen regions, awarding badges | Should |
| U-07 | WeChat social login for Chinese travelers | Could |
| U-08 | Loyalty points system with redeemable rewards | Won't (v1) |

### 2.5 Community Features

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| C-01 | Users can create and publish onsen diary entries (trip reports with photos and narrative) | Should |
| C-02 | Community feed displays latest onsen diaries with infinite scroll | Should |
| C-03 | Users can like and comment on diary entries | Should |
| C-04 | Seasonal recommendation collections (editorially curated) displayed on homepage and regional pages | Must |
| C-05 | User-submitted photos displayed in a community gallery on ryokan detail pages | Could |
| C-06 | Forum / discussion board for onsen travel advice | Won't (v1) |

### 2.6 Content & Education

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| E-01 | Onsen etiquette guide with illustrated step-by-step instructions | Must |
| E-02 | Onsen water type encyclopedia explaining each mineral type, therapeutic properties, and where to find them | Must |
| E-03 | Regional onsen area guides (Hakone, Kusatsu, Beppu, Kinosaki, etc.) with maps, seasonal tips, and transit access | Must |
| E-04 | Kaiseki dining guide explaining course structure and seasonal ingredients | Should |
| E-05 | Ryokan stay guide covering check-in etiquette, yukata wearing, tipping customs, and room layout | Should |
| E-06 | Tattoo policy guide with list of tattoo-friendly onsen and workaround options | Should |
| E-07 | Video content showing onsen experiences and ryokan tours | Could |

### 2.7 Internationalization

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| I-01 | Full UI translation in 5 languages: Japanese, English, Simplified Chinese, Traditional Chinese, Korean | Must |
| I-02 | URL-based locale routing (/en/..., /ja/..., /zh-cn/..., /zh-tw/..., /ko/...) | Must |
| I-03 | Auto-detect user language from browser Accept-Language header and Vercel geo headers | Must |
| I-04 | Currency display in JPY, USD, EUR, CNY, KRW with conversion rates updated daily | Must |
| I-05 | Date formatting respects locale conventions (YYYY/MM/DD for Japanese, MM/DD/YYYY for US, etc.) | Must |
| I-06 | Ryokan descriptions available in at least JP and EN; other languages progressively added | Must |
| I-07 | Right-to-left layout support for Arabic | Won't (v1) |

### 2.8 Ryokan Owner Portal

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| O-01 | Ryokan owners can manage listing details (photos, descriptions, amenities, onsen info) | Should |
| O-02 | Ryokan owners can manage room inventory and availability calendar | Should |
| O-03 | Ryokan owners can set pricing and seasonal rate adjustments | Should |
| O-04 | Ryokan owners can view and respond to bookings | Should |
| O-05 | Dashboard showing booking analytics, revenue, and review scores | Could |
| O-06 | LINE-based notification integration for new bookings | Could |

---

## 3. Non-Functional Requirements

| ID | Requirement | MoSCoW |
|----|-------------|--------|
| NF-01 | Page load time under 2 seconds on 4G connection for listing pages (LCP < 2.5s) | Must |
| NF-02 | Mobile-first responsive design working on iOS Safari, Android Chrome, and desktop Chrome/Firefox/Safari | Must |
| NF-03 | WCAG 2.1 AA accessibility compliance for core booking flow | Must |
| NF-04 | 99.9% uptime SLA (enabled by Vercel's global CDN and serverless architecture) | Must |
| NF-05 | GDPR and Japan APPI (Act on Protection of Personal Information) compliance for user data | Must |
| NF-06 | PCI DSS compliance delegated to Stripe (no card data stored on our servers) | Must |
| NF-07 | SEO optimization: server-rendered HTML, structured data (JSON-LD for LodgingBusiness), sitemap, meta tags | Must |
| NF-08 | Image optimization via next/image with WebP/AVIF format and responsive srcset | Must |
| NF-09 | Rate limiting on API routes (100 requests/minute per IP for search, 10/minute for booking) | Should |
| NF-10 | Progressive Web App with offline access to saved listings and guides | Could |

---

## 4. Component Inventory

All reusable UI components listed with parent-child hierarchy. Component names are canonical and must be referenced consistently across all documentation.

### 4.1 Layout Components

- **AppShell** — Root layout wrapper for all pages
  - **Header** — Top navigation bar with logo, search, locale selector, auth controls
    - **Logo** — OnsenBook brand mark and wordmark, links to homepage
    - **SearchBarCompact** — Collapsed search input in header (expands on focus)
    - **LocaleSelector** — Language dropdown switcher
    - **CurrencySelector** — Currency preference dropdown
    - **AuthButton** — Login/signup button or user avatar dropdown when authenticated
    - **UserMenuDropdown** — Dropdown menu with profile, bookings, wishlist, logout links
    - **MobileMenuToggle** — Hamburger icon to open mobile navigation drawer
  - **MobileDrawer** — Slide-out navigation panel for mobile viewports
  - **Footer** — Site-wide footer with links, legal info, language selector
    - **FooterLinkGroup** — Grouped navigation links within footer
    - **SocialLinks** — Social media icon links
  - **Breadcrumb** — Navigation breadcrumb trail for interior pages

### 4.2 Search & Filter Components

- **SearchHero** — Large search interface on homepage with destination, dates, guests inputs
  - **DestinationAutocomplete** — Autocomplete input powered by region database / Google Places
  - **DateRangePicker** — Check-in / check-out date selector
  - **GuestSelector** — Adults and children count selector with dropdown
- **SearchFiltersPanel** — Sidebar or modal containing all filter controls
  - **FilterGroup** — Collapsible section for a group of related filters
    - **OnsenTypeFilter** — Checkboxes for water mineral types
    - **BathStyleFilter** — Checkboxes for bath styles (outdoor, indoor, cave, etc.)
    - **PrivacyLevelFilter** — Checkboxes for privacy levels
    - **PriceRangeSlider** — Dual-handle range slider for min/max price
    - **MealPlanFilter** — Checkboxes for meal plan options
    - **TattooFilter** — Checkboxes for tattoo policies
    - **RatingFilter** — Minimum star rating selector
    - **AccessibilityFilter** — Checkboxes for accessibility features
  - **ActiveFilterTags** — Horizontal list of active filter badges with remove buttons
  - **FilterResetButton** — Button to clear all active filters
- **SearchSortDropdown** — Sort order selector (price, rating, distance, editorial pick)
- **SearchResultsList** — Container for search result cards with count header
  - **RyokanCard** — Summary card for a single ryokan in search results
    - **RyokanCardImage** — Primary photo with image carousel dots
    - **RyokanCardBadge** — Editorial pick, new listing, or deal badge overlay
    - **RyokanCardOnsenTags** — Compact tag list of onsen water types and bath styles
    - **RyokanCardPricing** — Per-person-per-night price with currency
    - **RyokanCardRating** — Star rating with review count
    - **WishlistToggle** — Heart icon button to save/unsave ryokan
- **SearchMapView** — Interactive Mapbox map displaying search results as pins
  - **MapPin** — Individual ryokan marker on the map
  - **MapPopup** — Mini ryokan card shown on pin click
- **SearchPagination** — Page navigation for search results

### 4.3 Ryokan Detail Components

- **RyokanDetailHero** — Full-width hero section with photo gallery and key info
  - **PhotoGallery** — Grid/carousel of categorized ryokan photos
    - **PhotoCategoryTab** — Tab to filter photos by category (rooms, baths, meals, etc.)
    - **PhotoLightbox** — Full-screen photo viewer overlay
  - **RyokanTitleBlock** — Name, location, star rating, review count, and badges
  - **QuickInfoBar** — Key facts row: check-in/out times, onsen hours, tattoo policy
- **OnsenDetailsSection** — Dedicated section for onsen/bath information
  - **OnsenTypeCard** — Card for each water type with mineral info, pH, temperature
  - **BathCard** — Card for each bath with style, photo, gender/hours info, and description
- **RoomTypeSection** — List of available room types
  - **RoomTypeCard** — Individual room option with photos, size, amenities, pricing
    - **RoomAmenitiesList** — Icon list of room amenities
    - **RoomSelectButton** — CTA to select this room and proceed to booking
- **MealPlanSection** — Meal plan details with seasonal menu examples
  - **MealPlanCard** — Card per meal plan option with course description and photos
- **ReviewsSection** — User reviews list with rating summary
  - **RatingBreakdown** — Bar chart showing rating distribution across subcategories
  - **ReviewCard** — Individual review with author, date, ratings, and text
  - **ReviewPagination** — Pagination control for review list
- **LocationSection** — Map and access information
  - **AccessDirections** — Transit and driving directions with estimated travel times
  - **NearbyAttractions** — List of nearby points of interest
- **SeasonalHighlightBanner** — Banner showing current season experience at this ryokan
- **SimilarRyokanSection** — Horizontal scroll of similar ryokan recommendations
  - (uses **RyokanCard** from Search components)
- **StickyBookingBar** — Fixed bottom bar (mobile) or sidebar CTA (desktop) with price and "Book Now"

### 4.4 Booking Flow Components

- **BookingSummaryCard** — Sidebar summary showing selected ryokan, room, dates, guests, price
- **BookingStepIndicator** — Step progress indicator (Select Room -> Guest Details -> Payment -> Confirmation)
- **GuestDetailsForm** — Form for guest names, contact, dietary restrictions, special requests
  - **GuestFieldGroup** — Repeated field group per guest
  - **DietaryRestrictionSelect** — Multi-select for dietary needs
  - **SpecialRequestTextarea** — Free-text area for special requests
  - **ArrivalTimeSelect** — Estimated arrival time dropdown
- **PaymentForm** — Stripe Elements embedded payment form
  - **CardInputField** — Stripe card number, expiry, CVC input
  - **BillingAddressForm** — Billing address fields
  - **PricingBreakdown** — Itemized price breakdown (room x nights x guests, taxes, fees)
  - **CouponCodeInput** — Optional promotional code input
- **BookingConfirmation** — Confirmation page with reservation details and next steps
  - **ReservationSummary** — Complete booking details recap
  - **AccessGuide** — How to reach the ryokan from major transit hubs
  - **EtiquetteQuickTips** — Brief onsen etiquette reminders
  - **AddToCalendarButton** — Button to add reservation to Google/Apple/Outlook calendar

### 4.5 User Account Components

- **AuthModal** — Modal dialog for login and registration
  - **LoginForm** — Email/password login form
  - **RegisterForm** — Registration form with name, email, password
  - **SocialLoginButtons** — Google and LINE social login buttons
  - **ForgotPasswordForm** — Password reset request form
- **UserDashboard** — Main dashboard layout for authenticated users
  - **DashboardNav** — Sidebar/tab navigation for dashboard sections
  - **UpcomingBookings** — List of future reservations
    - **BookingCard** — Summary card for a single booking with status and actions
  - **PastBookings** — List of completed stays with review prompts
  - **WishlistGrid** — Grid of saved/favorited ryokan
    - (uses **RyokanCard** from Search components)
  - **HotSpringPassport** — Visual map/grid of visited onsen regions with badges
    - **PassportStamp** — Individual region stamp (earned or locked)
    - **BadgeDisplay** — Achievement badge with name and description
  - **UserProfileForm** — Editable profile fields (name, language, currency, preferences)

### 4.6 Community Components

- **DiaryFeed** — Infinite-scroll feed of onsen diary entries
  - **DiaryCard** — Preview card for a diary entry with cover photo, title, excerpt, author
    - **DiaryCardAuthor** — Author avatar, name, and passport level
    - **DiaryCardStats** — Like count and comment count
  - **DiaryFeedFilter** — Filter/sort controls for diary feed (recent, popular, by region)
- **DiaryDetail** — Full diary entry view with rich text, photos, and linked ryokan
  - **DiaryContent** — Rendered rich text body with embedded images
  - **DiaryLinkedRyokan** — Card linking to the featured ryokan listing
  - **DiaryCommentSection** — Comment thread below diary
    - **CommentCard** — Individual comment with author and timestamp
    - **CommentForm** — Text input for adding a comment
  - **DiaryLikeButton** — Like/heart button with count
- **DiaryEditor** — Rich text editor for creating/editing diary entries
  - **DiaryTitleInput** — Title text input
  - **DiaryCoverImageUpload** — Cover photo upload with preview
  - **DiaryRichTextEditor** — WYSIWYG content editor with image embedding
  - **DiaryRyokanLinker** — Autocomplete to link diary to a ryokan listing
  - **DiaryPublishButton** — Save draft or publish button

### 4.7 Content & Education Components

- **GuidePageLayout** — Layout template for educational content pages
  - **GuideTableOfContents** — Sticky sidebar table of contents for long-form guides
  - **GuideContentBody** — Rendered markdown/rich text content area
  - **GuideRelatedLinks** — Related guides and ryokan links at bottom
- **RegionalGuideHero** — Hero section for regional onsen area guides with hero image and map
- **CuratedCollectionGrid** — Grid of ryokan for a curated theme (e.g., "Best Winter Onsen")
  - (uses **RyokanCard** from Search components)
- **OnsenTypeEncyclopediaEntry** — Detail view for a single onsen water type
- **EtiquetteStepCard** — Illustrated step in the onsen etiquette guide

### 4.8 Shared / Utility Components

- **LoadingSpinner** — Centered loading animation
- **LoadingSkeleton** — Placeholder skeleton screen matching target component shape
- **ErrorState** — Error message with retry button and optional illustration
- **EmptyState** — Empty state message with illustration and CTA
- **Toast** — Notification toast (success, error, info) via react-hot-toast
- **ConfirmDialog** — Confirmation modal for destructive actions (cancel booking, delete diary)
- **ShareButton** — Share via Web Share API or fallback modal with copy link
- **ImageWithFallback** — next/image wrapper with loading skeleton and error fallback
- **Badge** — Small label component for tags, status indicators
- **StarRating** — Star rating display (read-only) or interactive (for review input)
- **PriceDisplay** — Formatted price with currency symbol and per-unit label
- **Tooltip** — Information tooltip triggered on hover/focus

---

## 5. Responsive Breakpoint Strategy

### Breakpoint Definitions

| Name | Range | Tailwind Prefix | Primary Target |
|------|-------|-----------------|----------------|
| Mobile | < 768px | (default) | Smartphones in portrait |
| Tablet | 768px–1024px | `md:` | Tablets, small laptops |
| Desktop | > 1024px | `lg:` | Laptops, desktops |

### Global Responsive Behaviors

- **Navigation**: Mobile uses hamburger menu with **MobileDrawer**; tablet shows condensed header; desktop shows full **Header** with all navigation links visible.
- **Search Filters**: Mobile shows filters in a full-screen slide-up modal triggered by a filter button; tablet shows a collapsible sidebar; desktop shows a persistent left sidebar.
- **Grid Layouts**: Mobile uses single-column stacked layout; tablet uses 2-column grid; desktop uses 3-4 column grid for ryokan cards and content grids.
- **Maps**: Mobile shows map as a toggleable full-screen view (list/map toggle); tablet and desktop show map alongside the search results list in a split-pane layout.
- **Booking Sidebar**: Mobile shows **StickyBookingBar** as a fixed bottom bar with price and "Book Now" CTA; desktop shows full **BookingSummaryCard** in a sticky right sidebar.
- **Images**: All images use next/image with responsive srcset. Mobile serves smaller images (640w); tablet (1024w); desktop (1920w). Format: WebP with AVIF where supported.
- **Typography**: Base font size 16px. Headings scale down on mobile (h1: 24px mobile -> 36px desktop). Body text remains 16px across all breakpoints for readability.
- **Touch targets**: All interactive elements have minimum 44x44px touch targets on mobile per WCAG guidelines.

---

## 6. Route Structure

### Public Routes

| Route | Page | Rendering | Data Requirements |
|-------|------|-----------|-------------------|
| `/[locale]` | Homepage | SSG (daily rebuild) | Featured collections, seasonal highlights, popular regions, recent diaries |
| `/[locale]/search` | Search Results | SSR | Query params: destination, dates, guests, filters. Returns: ryokan list with availability, map pins |
| `/[locale]/ryokan/[slug]` | Ryokan Detail | ISR (60s) | Ryokan full details, onsen info, room types, review summary, availability, similar ryokan |
| `/[locale]/ryokan/[slug]/reviews` | All Reviews | ISR (60s) | Paginated reviews for a ryokan, rating breakdown |
| `/[locale]/regions/[region]` | Regional Guide | ISR (3600s) | Region details, editorial content, curated ryokan list, area map, seasonal tips |
| `/[locale]/onsen-guide` | Onsen Guide Index | SSG | List of all guide articles |
| `/[locale]/onsen-guide/[slug]` | Guide Article | SSG | Article content (markdown), related guides, related ryokan |
| `/[locale]/onsen-guide/etiquette` | Etiquette Guide | SSG | Illustrated step-by-step etiquette content |
| `/[locale]/onsen-guide/water-types` | Water Type Encyclopedia | SSG | All onsen water types with descriptions |
| `/[locale]/onsen-guide/water-types/[type]` | Water Type Detail | SSG | Single water type detail, ryokan with this water type |
| `/[locale]/community/diaries` | Diary Feed | ISR (60s) | Paginated diary entries, filter/sort options |
| `/[locale]/community/diaries/[id]` | Diary Detail | ISR (60s) | Diary content, comments, linked ryokan, author info |
| `/[locale]/collections/[slug]` | Curated Collection | ISR (3600s) | Collection metadata, curated ryokan list |
| `/[locale]/about` | About Page | SSG | Static content |
| `/[locale]/terms` | Terms of Service | SSG | Static content |
| `/[locale]/privacy` | Privacy Policy | SSG | Static content |

### Authenticated Routes

| Route | Page | Rendering | Data Requirements |
|-------|------|-----------|-------------------|
| `/[locale]/booking/[ryokanSlug]` | Booking Flow | SSR | Real-time room availability, pricing, Stripe payment intent |
| `/[locale]/booking/confirmation/[bookingId]` | Booking Confirmation | SSR | Booking details, access guide, etiquette tips |
| `/[locale]/dashboard` | User Dashboard | SSR | User profile, upcoming bookings, past bookings summary |
| `/[locale]/dashboard/bookings` | All Bookings | SSR | Full booking history with status |
| `/[locale]/dashboard/bookings/[bookingId]` | Booking Detail | SSR | Single booking details with modification/cancel options |
| `/[locale]/dashboard/wishlist` | Wishlist | SSR | Saved ryokan list with current pricing |
| `/[locale]/dashboard/passport` | Hot Spring Passport | SSR | Visited regions, badges earned, progress stats |
| `/[locale]/dashboard/profile` | Profile Settings | SSR | User profile data, preferences |
| `/[locale]/dashboard/reviews` | My Reviews | SSR | User's submitted reviews |
| `/[locale]/community/diaries/new` | Create Diary | SSR | Ryokan autocomplete for linking, image upload |
| `/[locale]/community/diaries/[id]/edit` | Edit Diary | SSR | Existing diary content for editing |

### Auth Routes

| Route | Page | Rendering | Data Requirements |
|-------|------|-----------|-------------------|
| `/[locale]/auth/login` | Login | SSR | None (form only); redirect URL param |
| `/[locale]/auth/register` | Register | SSR | None (form only) |
| `/[locale]/auth/forgot-password` | Forgot Password | SSR | None (form only) |
| `/[locale]/auth/reset-password` | Reset Password | SSR | Token validation |

### API Routes

| Route | Method | Purpose |
|-------|--------|---------|
| `/api/search` | GET | Search ryokan with filters, returns paginated results |
| `/api/ryokan/[slug]/availability` | GET | Real-time availability for date range |
| `/api/ryokan/[slug]/reviews` | GET/POST | Fetch or submit reviews |
| `/api/booking` | POST | Create a new booking |
| `/api/booking/[id]` | GET/PATCH/DELETE | Read, modify, or cancel booking |
| `/api/booking/[id]/payment-intent` | POST | Create Stripe payment intent |
| `/api/user/wishlist` | GET/POST/DELETE | Manage wishlist |
| `/api/user/profile` | GET/PATCH | Read or update user profile |
| `/api/community/diaries` | GET/POST | Fetch feed or create diary |
| `/api/community/diaries/[id]` | GET/PATCH/DELETE | Read, update, or delete diary |
| `/api/community/diaries/[id]/comments` | GET/POST | Fetch or add comments |
| `/api/community/diaries/[id]/like` | POST/DELETE | Like or unlike a diary |
| `/api/webhooks/stripe` | POST | Stripe webhook for payment events |
| `/api/upload/image` | POST | Image upload to Supabase Storage |
| `/api/geocode` | GET | Proxy for Google Places autocomplete |

---

## 7. Data Flow Description

### 7.1 Search Flow

```
User Input (SearchHero / SearchFiltersPanel)
  -> URL search params updated via nuqs (type-safe URL state)
  -> Client sends GET /api/search with query params (destination, dates, guests, filters, sort, page)
  -> API Route validates params with Zod schema
  -> Supabase query: JOIN ryokan, rooms, onsen_details, reviews tables with filter/sort/pagination
  -> If dates specified: check room_availability table for open inventory
  -> Response: { results: RyokanCard[], total: number, filters_applied: object }
  -> React Query caches response, keyed by search params (staleTime: 30s)
  -> SearchResultsList renders RyokanCard components
  -> SearchMapView receives same results, renders MapPin components
  -> User changes filter -> nuqs updates URL -> React Query refetches with new params -> UI updates
  -> SearchPagination triggers page param change -> same flow
```

### 7.2 Ryokan Detail Flow

```
Page Load (ISR: /ryokan/[slug])
  -> Server Component fetches from Supabase: ryokan details, onsen info, room types, review summary
  -> Static HTML generated and cached at CDN edge (revalidate: 60s)
  -> Client hydration activates interactive components
  -> PhotoGallery: images loaded via next/image from Supabase Storage CDN
  -> ReviewsSection: initial reviews SSR'd; "Load More" triggers client-side /api/ryokan/[slug]/reviews
  -> Availability check: Client calls /api/ryokan/[slug]/availability with selected dates
  -> StickyBookingBar / RoomSelectButton: price updates based on availability response
  -> WishlistToggle: Client calls /api/user/wishlist (POST/DELETE) — optimistic UI update via React Query
  -> SimilarRyokanSection: Server Component fetches similar ryokan by region + onsen type
```

### 7.3 Booking Flow

```
Step 1: Room Selection (from Ryokan Detail)
  -> User clicks RoomSelectButton -> navigates to /booking/[ryokanSlug]?room=[roomId]&checkin=...&checkout=...&guests=...
  -> SSR page fetches real-time availability + pricing from Supabase
  -> BookingSummaryCard displays selected room, dates, calculated total
  -> BookingStepIndicator shows Step 1 (already selected) -> Step 2 active

Step 2: Guest Details
  -> GuestDetailsForm collects information via react-hook-form
  -> Client-side Zod validation on each field
  -> Data stored in React state (not persisted until payment)

Step 3: Payment
  -> Client calls /api/booking/[id]/payment-intent -> creates Stripe PaymentIntent
  -> Stripe Elements (CardInputField) renders secure card input
  -> PricingBreakdown shows itemized costs (room, meals, taxes, service fee)
  -> User submits -> Stripe processes payment -> PaymentIntent succeeds/fails
  -> On success: /api/booking creates booking record in Supabase (status: confirmed)
  -> On failure: ErrorState displayed with retry option

Step 4: Confirmation (Async via Stripe Webhook)
  -> Stripe sends payment_intent.succeeded webhook to /api/webhooks/stripe
  -> Webhook handler: updates booking status, sends confirmation email via Resend, notifies ryokan
  -> User redirected to /booking/confirmation/[bookingId]
  -> BookingConfirmation renders reservation details from Supabase
  -> AddToCalendarButton generates .ics file or Google Calendar link
```

### 7.4 Community Diary Flow

```
Create:
  -> Authenticated user navigates to /community/diaries/new
  -> DiaryEditor: DiaryTitleInput + DiaryCoverImageUpload + DiaryRichTextEditor + DiaryRyokanLinker
  -> Image uploads -> /api/upload/image -> Supabase Storage -> returns public URL
  -> DiaryRyokanLinker -> /api/search (autocomplete mode) -> links diary to ryokan record
  -> DiaryPublishButton -> /api/community/diaries (POST) -> creates diary record in Supabase
  -> On success: redirect to /community/diaries/[id]

Read:
  -> DiaryFeed: ISR page fetches recent diaries from Supabase (paginated)
  -> Infinite scroll: client calls /api/community/diaries?page=N for next page via React Query
  -> DiaryDetail: ISR page fetches single diary with comments
  -> DiaryLikeButton: /api/community/diaries/[id]/like (POST/DELETE) -> optimistic UI update
  -> DiaryCommentSection: CommentForm -> /api/community/diaries/[id]/comments (POST)
```

### 7.5 Authentication Flow

```
Login/Register:
  -> AuthModal opens (triggered by AuthButton or protected route redirect)
  -> Email/password: LoginForm -> NextAuth signIn("credentials") -> JWT session
  -> Social: SocialLoginButtons -> NextAuth signIn("google"|"line") -> OAuth flow -> JWT session
  -> On success: AuthModal closes, Header updates to show UserMenuDropdown
  -> Session stored as HTTP-only cookie, validated server-side on SSR pages

Protected Routes:
  -> Next.js middleware checks session cookie on /dashboard/*, /booking/*, /community/diaries/new
  -> No valid session -> redirect to /auth/login?redirect=[original_url]
  -> Valid session -> proceed, inject user context into server components
```

### 7.6 Internationalization Flow

```
Request arrives at Vercel Edge:
  -> Edge middleware reads: (1) URL locale prefix, (2) cookie locale preference, (3) Accept-Language header, (4) Vercel geo headers
  -> Priority: URL prefix > cookie > Accept-Language > geo > default (en)
  -> If no locale in URL: redirect to /[detected_locale]/...
  -> next-intl loads message bundle for active locale (namespace-split per route)
  -> CurrencySelector preference stored in cookie, used by PriceDisplay component
  -> Intl.NumberFormat formats prices; Intl.DateTimeFormat formats dates per locale
  -> LocaleSelector change -> navigates to new locale prefix URL, sets cookie
```

---

## 8. Data Models (Key Entities)

### Ryokan
```
ryokan: {
  id, slug, name (jsonb: {ja, en, zh_cn, zh_tw, ko}), description (jsonb),
  region_id, prefecture, city, address, latitude, longitude,
  price_range_min, price_range_max, star_rating, review_count, review_avg,
  checkin_time, checkout_time, cancellation_policy,
  tattoo_policy, accessibility_features (jsonb),
  is_editorial_pick, editorial_score,
  photos (relation), onsen_details (relation), room_types (relation),
  meal_plans (relation), created_at, updated_at, status
}
```

### Onsen Detail
```
onsen_detail: {
  id, ryokan_id, water_type (enum), ph_level, temperature_celsius,
  source_type (natural|heated|mixed), bath_style (enum),
  privacy_level (enum), gender (mixed|male|female),
  operating_hours, description (jsonb), photos (relation),
  therapeutic_benefits (jsonb array)
}
```

### Room Type
```
room_type: {
  id, ryokan_id, name (jsonb), description (jsonb),
  tatami_size_jo, max_occupancy, bed_configuration,
  has_private_bath, view_type, amenities (jsonb array),
  base_price_per_person, photos (relation)
}
```

### Booking
```
booking: {
  id, user_id, ryokan_id, room_type_id,
  checkin_date, checkout_date, guest_count_adults, guest_count_children,
  meal_plan_id, total_price_jpy, currency_charged, amount_charged,
  stripe_payment_intent_id, status (pending|confirmed|cancelled|completed),
  guest_details (jsonb), special_requests,
  created_at, updated_at
}
```

### User
```
user: {
  id, email, name, avatar_url,
  preferred_locale, preferred_currency,
  auth_provider, auth_provider_id,
  passport_stamps (relation), wishlist (relation),
  created_at
}
```

### Review
```
review: {
  id, user_id, ryokan_id, booking_id,
  rating_overall, rating_onsen, rating_hospitality,
  rating_meals, rating_atmosphere, rating_cleanliness,
  text, language, created_at, updated_at
}
```

### Diary
```
diary: {
  id, author_id, title, cover_image_url,
  content (rich text / jsonb), ryokan_id (nullable),
  region_id (nullable), status (draft|published),
  like_count, comment_count,
  published_at, created_at, updated_at
}
```

---

## 9. Third-Party Integrations

| Service | Purpose | Integration Point |
|---------|---------|-------------------|
| Supabase | Database, Auth (optional), Storage, Real-time | Server components, API routes, client SDK |
| Stripe | Payments, Connect (marketplace payouts) | API routes, client-side Stripe Elements |
| Mapbox GL JS | Interactive maps | Client component (react-map-gl), dynamically imported |
| Google Places API | Location autocomplete | API route proxy (/api/geocode) |
| NextAuth.js | Authentication orchestration | Auth routes, middleware, session management |
| Vercel Image Optimization | Image resizing/format conversion | next/image component |
| next-intl | Internationalization | Middleware, server/client components |
| React Query | Client-side data fetching/caching | Client components for search, availability, user data |
| Resend | Transactional email | API routes for booking confirmation, notifications |

---

## 10. Security Considerations

- All user input validated server-side with Zod schemas (never trust client-only validation)
- Supabase Row Level Security (RLS) policies enforce data access at the database level
- Stripe webhook signature verification on /api/webhooks/stripe
- CSRF protection via SameSite cookies and origin checking
- Image uploads validated for file type and size (max 10MB per image, JPEG/PNG/WebP only)
- Rate limiting on search (100 req/min/IP), booking (10 req/min/IP), and auth (5 req/min/IP) endpoints
- Sensitive data (payment info) never stored — delegated entirely to Stripe
- Content Security Policy headers configured in next.config.js
