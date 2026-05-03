# Backend System Design Interview Template

## How to Tackle a System Design Interview Question

The system design interview is an open-ended conversation. **You are expected to lead it.**

Use the following steps to guide the discussion.

---

## Step 1: Outline Use Cases, Constraints, and Assumptions

**Gather requirements and scope the problem. Ask questions to clarify use cases and constraints. Discuss assumptions.**

### Questions to Ask:

* **Who is going to use it?**
* **How are they going to use it?**
* **How many users are there?**
* **What does the system do?**
* **What are the inputs and outputs of the system?**
* **How much data do we expect to handle?**
* **How many requests per second do we expect?**
* **What is the expected read to write ratio?**

### Document Your Understanding:

* **Users:** [Number of users, user types, geographic distribution]
* **Use Cases:** [Primary workflows, user journeys]
* **Scale:** [Requests/second, data volume, growth rate]
* **Constraints:** [Budget, latency requirements, availability needs]
* **Assumptions:** [What you're assuming is true - call these out explicitly]

---

## Step 2: Create a High-Level Design

**Outline a high-level design with all important components.**

### Actions:

* **Sketch the main components and connections**
  * Client (Web, Mobile, API consumers)
  * API Gateway / Load Balancer
  * Application Servers
  * Database(s)
  * Cache Layer
  * Message Queue (if async processing needed)
  * External Services

* **Justify your ideas**
  * Why this architecture?
  * What are the key data flows?
  * Where might bottlenecks occur?

### Example High-Level Architecture:
```
┌─────────────┐
│   Clients   │
│ (Web/Mobile)│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│Load Balancer│
└──────┬──────┘
       │
       ▼
┌─────────────────────────────┐
│   Application Servers       │
│   (Stateless, Horizontally  │
│    Scalable)                │
└────┬─────────────────┬──────┘
     │                 │
     ▼                 ▼
┌─────────┐      ┌──────────┐
│  Cache  │      │ Database │
│ (Redis) │      │(SQL/NoSQL)│
└─────────┘      └──────────┘
     │                 │
     └────────┬────────┘
              ▼
        ┌──────────┐
        │  Queue   │
        │ (RabbitMQ│
        │  /Kafka) │
        └──────────┘
              │
              ▼
        ┌──────────┐
        │  Worker  │
        │ Processes│
        └──────────┘
```

---

## Step 3: Design Core Components

**Dive into details for each core component.**

### Example: Design a URL Shortening Service

**Component 1: Generating and Storing a Hash**

* **Hashing Algorithm:**
  * **MD5:** Fast, but 128-bit output is too long
  * **Base62 Encoding:** Use first 7 characters for ~3.5 trillion URLs
  * **Custom Hash:** Generate random string, check for collisions

* **Hash Collisions:**
  * Probability increases with scale (Birthday Paradox)
  * Check database before inserting
  * Retry with different seed if collision occurs

* **Database Choice:**
  * **SQL (PostgreSQL):**
    * ACID guarantees
    * Good for relational data
    * Easier to maintain consistency
  
  * **NoSQL (DynamoDB, Cassandra):**
    * Better horizontal scaling
    * Higher write throughput
    * Eventual consistency trade-off

* **Database Schema:**
```sql
-- SQL Example
CREATE TABLE urls (
    short_code VARCHAR(10) PRIMARY KEY,
    original_url TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP,
    user_id INTEGER,
    click_count INTEGER DEFAULT 0,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
);

CREATE TABLE clicks (
    id SERIAL PRIMARY KEY,
    short_code VARCHAR(10) REFERENCES urls(short_code),
    clicked_at TIMESTAMP DEFAULT NOW(),
    user_agent TEXT,
    ip_address INET,
    referrer TEXT
);
```

**Component 2: Translating a Hashed URL to the Full URL**

* **Database Lookup:**
  * Query by `short_code` (primary key → fast)
  * Return `original_url`
  * Increment `click_count`

* **Caching Strategy:**
  * Cache popular URLs in Redis
  * TTL based on access frequency
  * Cache invalidation on URL deletion

**Component 3: API and Object-Oriented Design**

* **API Endpoints:**
```
POST /api/shorten
Request: {"url": "https://example.com/very/long/url"}
Response: {"short_url": "https://short.ly/abc123"}

GET /:short_code
Response: 301 Redirect to original URL

GET /api/stats/:short_code
Response: {"clicks": 1234, "created": "2024-03-15", ...}

DELETE /api/:short_code
Response: 204 No Content
```

* **Classes/Objects:**
```python
class URLShortener:
    def __init__(self, db_connection, cache):
        self.db = db_connection
        self.cache = cache
    
    def shorten_url(self, original_url, user_id=None):
        # Generate hash
        short_code = self.generate_hash(original_url)
        
        # Check for collision
        while self.db.exists(short_code):
            short_code = self.generate_hash(original_url, salt=random())
        
        # Save to database
        self.db.insert(short_code, original_url, user_id)
        
        return f"https://short.ly/{short_code}"
    
    def resolve_url(self, short_code):
        # Check cache first
        if url := self.cache.get(short_code):
            self.db.increment_clicks(short_code)
            return url
        
        # Fallback to database
        url = self.db.get_url(short_code)
        if url:
            self.cache.set(short_code, url, ttl=3600)
            self.db.increment_clicks(short_code)
            return url
        
        raise URLNotFoundError()
```

---

## Step 4: Scale the Design

**Identify and address bottlenecks, given the constraints.**

### Questions to Address:

* Do you need a **load balancer**?
* Do you need **horizontal scaling**?
* Do you need **caching**?
* Do you need **database sharding**?

### Discuss Potential Solutions and Trade-offs

**Everything is a trade-off.** Address bottlenecks using principles of scalable system design.

---

### Scaling Technique 1: Load Balancing

**When to Use:**
* Multiple application servers
* Need to distribute traffic evenly
* Want high availability

**Implementation:**
* **Layer 4 (TCP) Load Balancer:** Fast, simple routing
* **Layer 7 (HTTP) Load Balancer:** Can route based on URL, headers
* **DNS Round Robin:** Simplest, but no health checks

**Trade-offs:**
* ✅ Distributes load, handles failures
* ❌ Single point of failure (need redundancy)
* ❌ Adds latency (minimal, ~1ms)

**Popular Tools:**
* Nginx, HAProxy, AWS ALB/NLB, Google Cloud Load Balancing

---

### Scaling Technique 2: Horizontal Scaling

**When to Use:**
* Single server hitting CPU/memory limits
* Traffic is unpredictable (need auto-scaling)
* Want to scale incrementally

**Implementation:**
* **Stateless Application Servers:**
  * No session data stored locally
  * Session in Redis/database
  * Any server can handle any request

* **Auto-Scaling:**
  * Based on CPU, memory, request rate
  * Kubernetes Horizontal Pod Autoscaler
  * AWS Auto Scaling Groups

**Trade-offs:**
* ✅ Scales to handle more load
* ✅ Fault-tolerant (one server fails, others handle traffic)
* ❌ More complex deployment
* ❌ Need load balancer

---

### Scaling Technique 3: Caching

**When to Use:**
* Repeated reads of same data (read-heavy workload)
* Database queries are slow
* Want to reduce database load

**Cache Layers:**

1. **Client-side Cache:**
   * Browser cache, localStorage
   * CDN for static assets
   
2. **Application-level Cache:**
   * In-memory (limited by RAM)
   * Redis, Memcached
   
3. **Database Query Cache:**
   * Built-in to most databases
   * Caches query results

**Cache Strategies:**

* **Cache-Aside (Lazy Loading):**
  * Read from cache first
  * On miss, read from DB and populate cache
  * App manages cache explicitly

* **Write-Through:**
  * Write to cache and DB simultaneously
  * Ensures cache is always up-to-date
  * Higher write latency

* **Write-Behind:**
  * Write to cache immediately
  * Async write to DB in background
  * Risk of data loss if cache fails

**Cache Invalidation:**
* TTL (Time-To-Live)
* Explicit invalidation on updates
* LRU (Least Recently Used) eviction

**Trade-offs:**
* ✅ Dramatically faster reads
* ✅ Reduces database load
* ❌ Adds complexity (cache invalidation is hard)
* ❌ Eventual consistency issues
* ❌ Additional infrastructure cost

---

### Scaling Technique 4: Database Sharding

**When to Use:**
* Single database can't handle write load
* Database storage exceeds single node capacity
* Need geographical distribution

**Sharding Strategies:**

1. **Horizontal Sharding (Range-based):**
   * Shard by user ID: Users 1-1M → Shard 1, 1M-2M → Shard 2
   * ✅ Simple to implement
   * ❌ Can create "hot" shards (uneven distribution)

2. **Hash-based Sharding:**
   * Hash user ID, mod by number of shards
   * ✅ Even distribution
   * ❌ Hard to add/remove shards (rehashing)

3. **Geo-based Sharding:**
   * US users → US DB, EU users → EU DB
   * ✅ Low latency for users
   * ❌ Complex cross-region queries

**Challenges:**
* **Cross-shard Queries:**
  * Joins across shards are expensive
  * Denormalize data or use application-level joins

* **Shard Key Selection:**
  * Must evenly distribute data
  * Rarely changes (user ID good, location bad)

* **Rebalancing:**
  * Adding new shards requires data migration
  * Use consistent hashing to minimize movement

**Trade-offs:**
* ✅ Scales writes and storage
* ✅ Can distribute geographically
* ❌ Much more complex
* ❌ Transactions across shards are hard
* ❌ Application must be shard-aware

---

### Scaling Technique 5: Asynchronous Processing

**When to Use:**
* Long-running tasks (video processing, report generation)
* Tasks that don't need immediate response
* Want to smooth out load spikes

**Implementation:**

* **Message Queue:**
  * RabbitMQ, AWS SQS, Google Pub/Sub, Kafka
  * Producer adds tasks to queue
  * Workers consume and process tasks

* **Background Workers:**
  * Celery (Python), Sidekiq (Ruby), Bull (Node.js)
  * Can scale workers independently

**Example: Video Processing**
```
User uploads video → API accepts, returns "Processing..."
                  ↓
              Add to queue
                  ↓
          Worker picks up task
                  ↓
       Transcode, generate thumbnails
                  ↓
        Update database, notify user
```

**Trade-offs:**
* ✅ Improves API response time
* ✅ Decouples services
* ✅ Can retry failed tasks
* ❌ Adds complexity
* ❌ Need to handle failures and retries
* ❌ Eventual consistency

---

### Scaling Technique 6: Database Replication

**When to Use:**
* Read-heavy workload (read:write ratio > 10:1)
* Need high availability
* Want to reduce read latency

**Primary-Replica (Master-Slave):**
* **Primary:** Handles all writes
* **Replicas:** Handle reads
* Replication lag (eventual consistency)

**Multi-Primary (Master-Master):**
* Multiple nodes accept writes
* Conflict resolution needed
* Higher complexity

**Trade-offs:**
* ✅ Scales reads
* ✅ High availability (failover to replica)
* ❌ Replication lag (stale reads)
* ❌ Write scaling limited to primary

---

### Scaling Technique 7: CDN (Content Delivery Network)

**When to Use:**
* Serving static assets (images, CSS, JS)
* Global user base
* Want to reduce server load

**How It Works:**
* Cache content at edge locations globally
* User routed to nearest edge server
* Reduces latency and origin server load

**Trade-offs:**
* ✅ Fast content delivery
* ✅ Reduces bandwidth costs
* ❌ Costs money (Cloudflare, AWS CloudFront)
* ❌ Cache invalidation delays

---

### Scaling Technique 8: Microservices

**When to Use:**
* Monolith is too large to manage
* Different components have different scaling needs
* Want independent deployment

**Example Breakdown:**
```
Monolith:
┌────────────────────────┐
│  User Service          │
│  Order Service         │
│  Payment Service       │
│  Notification Service  │
└────────────────────────┘

Microservices:
┌────────┐  ┌────────┐  ┌─────────┐  ┌──────────┐
│  User  │  │ Order  │  │ Payment │  │  Notify  │
│ Service│  │Service │  │ Service │  │  Service │
└────────┘  └────────┘  └─────────┘  └──────────┘
```

**Trade-offs:**
* ✅ Independent scaling
* ✅ Independent deployment
* ✅ Team autonomy
* ❌ Much more complex (networking, monitoring)
* ❌ Distributed transactions are hard
* ❌ Higher operational overhead

---

## Common System Design Patterns

### 1. CQRS (Command Query Responsibility Segregation)

* Separate read and write models
* Optimized databases for each
* Event sourcing for consistency

### 2. Event-Driven Architecture

* Services communicate via events
* Decoupled, scalable
* Eventual consistency

### 3. Saga Pattern

* Distributed transactions across services
* Choreography or orchestration
* Compensation for rollbacks

### 4. Circuit Breaker

* Prevent cascading failures
* Fail fast when dependency is down
* Automatic recovery detection

### 5. API Gateway

* Single entry point for clients
* Rate limiting, authentication
* Request routing to services

---

## Key Metrics to Consider

### Availability
* **Target:** 99.9% (8.76 hours downtime/year) vs 99.99% (52.56 min/year)
* **How:** Redundancy, load balancing, failover

### Latency
* **Target:** p99 < 200ms for API responses
* **How:** Caching, CDN, database optimization

### Throughput
* **Target:** 10,000 requests/second
* **How:** Horizontal scaling, load balancing

### Consistency
* **Strong Consistency:** Always latest data (SQL transactions)
* **Eventual Consistency:** Eventually correct (NoSQL, replicas)
* **CAP Theorem:** Can't have all three (Consistency, Availability, Partition Tolerance)

---

## Trade-offs to Discuss

### 1. SQL vs NoSQL

**SQL (PostgreSQL, MySQL):**
* ✅ ACID guarantees, strong consistency
* ✅ Complex queries, joins
* ✅ Well-understood, mature
* ❌ Harder to scale horizontally
* ❌ Fixed schema

**NoSQL (MongoDB, DynamoDB, Cassandra):**
* ✅ Horizontal scaling
* ✅ Flexible schema
* ✅ High write throughput
* ❌ Eventual consistency
* ❌ Limited query capabilities

### 2. Synchronous vs Asynchronous

**Synchronous:**
* ✅ Immediate response
* ✅ Simpler to reason about
* ❌ Slower, blocks waiting
* ❌ Tight coupling

**Asynchronous:**
* ✅ Fast response (non-blocking)
* ✅ Decoupled services
* ❌ More complex (error handling, retries)
* ❌ Eventual consistency

### 3. Monolith vs Microservices

**Monolith:**
* ✅ Simpler to develop and deploy
* ✅ Easier to debug
* ❌ Hard to scale parts independently
* ❌ Large codebase, slower development

**Microservices:**
* ✅ Independent scaling and deployment
* ✅ Team autonomy
* ❌ Much more complex
* ❌ Network overhead, distributed debugging

---

## Common Interview Questions

### 1. Design a URL Shortener (like bit.ly)
* Hashing algorithms (MD5, Base62)
* Database schema
* Caching strategy
* Analytics tracking

### 2. Design Twitter
* User timeline generation
* Tweet storage and retrieval
* Fan-out on write vs fan-out on read
* Trending topics

### 3. Design Instagram
* Image storage and CDN
* Feed generation
* Like/comment aggregation
* Activity feed

### 4. Design Uber
* Geospatial indexing (QuadTree, Geohash)
* Real-time location updates
* Matching algorithm
* Payment processing

### 5. Design Netflix
* Video encoding and storage
* Recommendation engine
* CDN for streaming
* User profiles and watch history

### 6. Design WhatsApp
* Real-time messaging (WebSockets)
* Message storage
* Group chats
* Delivery and read receipts

### 7. Design Google Drive
* File storage (chunks, deduplication)
* Sync across devices
* Sharing and permissions
* Version control

### 8. Design YouTube
* Video upload and processing
* Streaming infrastructure
* Recommendation algorithm
* Comment and like system

---

## Final Checklist

Before ending the interview, make sure you've covered:

- [ ] **Clarified requirements** (users, scale, constraints)
- [ ] **Drawn high-level architecture** (with justification)
- [ ] **Designed core components** (with details)
- [ ] **Identified bottlenecks** (and proposed solutions)
- [ ] **Discussed trade-offs** (why this choice over alternatives)
- [ ] **Addressed scalability** (how to handle 10x, 100x growth)
- [ ] **Mentioned monitoring** (how to detect issues)
- [ ] **Considered failure cases** (what happens when X fails?)

---

## Resources

* [System Design Primer (GitHub)](https://github.com/donnemartin/system-design-primer)
* [Designing Data-Intensive Applications (Book)](https://dataintensive.net/)
* [High Scalability Blog](http://highscalability.com/)
* [AWS Architecture Center](https://aws.amazon.com/architecture/)
* [Google Cloud Architecture](https://cloud.google.com/architecture)

---

**Remember:** There's no single "correct" answer in system design. Focus on:
1. Understanding the problem
2. Making reasonable assumptions
3. Justifying your decisions
4. Discussing trade-offs
5. Showing you can think at scale

**Good luck!**

---

**Last Updated:** 28-03-2026
**Version:** 1.0  
**Author:** Praizdev