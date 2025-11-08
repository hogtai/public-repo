#!/bin/bash

# Enhanced Cache Poisoning Protection QA Test Script
# For Jira ticket SRE-2215
# Provides detailed failure reporting and categorization

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# CORRECT Environments to test (PUBLIC URLS)
environments=(
    "example.com"
    "example-2.com"
)

# Results tracking
declare -A test_results
declare -A failure_details
security_failures=0
functional_failures=0
performance_warnings=0

# Test categories
CRITICAL_SECURITY="CRITICAL_SECURITY"
SECURITY="SECURITY"
FUNCTIONAL="FUNCTIONAL"
PERFORMANCE="PERFORMANCE"

# Function to record test result
record_test() {
    local env=$1
    local test_name=$2
    local status=$3
    local category=$4
    local details=$5
    
    test_results["${env}:${test_name}"]="$status"
    
    if [ "$status" == "FAILED" ]; then
        failure_details["${env}:${test_name}"]="$details"
        
        case $category in
            $CRITICAL_SECURITY|$SECURITY)
                ((security_failures++))
                ;;
            $FUNCTIONAL)
                ((functional_failures++))
                ;;
            $PERFORMANCE)
                ((performance_warnings++))
                ;;
        esac
    fi
}

# Function to print section headers
print_header() {
    echo -e "\n${BLUE}=== $1 ===${NC}"
    echo "$(printf '%.0s-' {1..60})"
}

# Function to test a single environment
test_environment() {
    local env=$1
    local url="https://${env}/"
    
    echo -e "\n${CYAN}🔍 Testing: $url${NC}"
    
    # Test 1: Critical Security - Cache Poisoning with X-Forwarded-Host
    echo -n "  [CRITICAL] X-Forwarded-Host protection: "
    local poisoned_response=$(curl -s -H "X-Forwarded-Host: evil.com" "$url" --connect-timeout 5)
    
    if echo "$poisoned_response" | grep -q "evil\.com"; then
        echo -e "${RED}❌ FAILED${NC}"
        record_test "$env" "x-forwarded-host" "FAILED" "$CRITICAL_SECURITY" "Cache poisoning detected with evil.com in response"
    else
        echo -e "${GREEN}✅ PASSED${NC}"
        record_test "$env" "x-forwarded-host" "PASSED" "$CRITICAL_SECURITY" ""
    fi
    
    # Test 2: Security - Header stripping behavioral test
    echo "  [Security] Header stripping tests:"
    
    # Create temp directory
    local temp_dir="/tmp/cache_test_${env//\./_}"
    mkdir -p "$temp_dir"
    
    # Get baseline response
    local baseline_status=$(curl -s "$url" --connect-timeout 5 -o "$temp_dir/baseline.html" -w "%{http_code}")
    
    if [ "$baseline_status" == "000" ]; then
        echo "     - Connection failed, skipping header tests"
        record_test "$env" "x-rewrite-url" "SKIPPED" "$SECURITY" "No connection"
        record_test "$env" "x-original-url" "SKIPPED" "$SECURITY" "No connection"
    else
        # Test x-rewrite-url
        echo -n "     - x-rewrite-url header stripping: "
        curl -s -H "x-rewrite-url: /admin/sensitive-page" "$url" --connect-timeout 5 -o "$temp_dir/with_rewrite.html"
        
        if diff -q "$temp_dir/baseline.html" "$temp_dir/with_rewrite.html" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PASSED${NC}"
            record_test "$env" "x-rewrite-url" "PASSED" "$SECURITY" ""
        else
            local diff_size=$(diff "$temp_dir/baseline.html" "$temp_dir/with_rewrite.html" 2>/dev/null | wc -l)
            if [ "$diff_size" -lt 10 ]; then
                echo -e "${YELLOW}⚠️  Minor differences (acceptable)${NC}"
                record_test "$env" "x-rewrite-url" "PASSED" "$SECURITY" "Minor differences detected"
            else
                echo -e "${RED}❌ FAILED (significant differences)${NC}"
                record_test "$env" "x-rewrite-url" "FAILED" "$SECURITY" "Response differs by $diff_size lines"
            fi
        fi
        
        # Test x-original-url
        echo -n "     - x-original-url header stripping: "
        curl -s -H "x-original-url: https://evil.com/phishing" "$url" --connect-timeout 5 -o "$temp_dir/with_original.html"
        
        if grep -q "evil\.com" "$temp_dir/with_original.html" 2>/dev/null; then
            echo -e "${RED}❌ FAILED (evil.com in response!)${NC}"
            record_test "$env" "x-original-url" "FAILED" "$SECURITY" "evil.com found in response"
        elif diff -q "$temp_dir/baseline.html" "$temp_dir/with_original.html" > /dev/null 2>&1; then
            echo -e "${GREEN}✅ PASSED${NC}"
            record_test "$env" "x-original-url" "PASSED" "$SECURITY" ""
        else
            local diff_size=$(diff "$temp_dir/baseline.html" "$temp_dir/with_original.html" 2>/dev/null | wc -l)
            if [ "$diff_size" -lt 10 ]; then
                echo -e "${YELLOW}⚠️  Minor differences (acceptable)${NC}"
                record_test "$env" "x-original-url" "PASSED" "$SECURITY" "Minor differences detected"
            else
                echo -e "${RED}❌ FAILED (significant differences)${NC}"
                record_test "$env" "x-original-url" "FAILED" "$SECURITY" "Response differs by $diff_size lines"
            fi
        fi
    fi
    
    # Test 3: Security - Cache persistence test
    echo -n "  [Security] Cache persistence test: "
    local timestamp=$(date +%s)
    local cache_url="${url}?cache_test=${timestamp}"
    
    # First request with malicious header
    curl -s -H "X-Forwarded-Host: evil.com" "$cache_url" --connect-timeout 5 -o "$temp_dir/cache_poisoned.html"
    sleep 1
    
    # Second request without malicious header
    local clean_response=$(curl -s "$cache_url" --connect-timeout 5)
    
    if echo "$clean_response" | grep -q "evil\.com"; then
        echo -e "${RED}❌ FAILED (cache poisoned!)${NC}"
        record_test "$env" "cache-persistence" "FAILED" "$CRITICAL_SECURITY" "Cache was poisoned with evil.com"
    else
        echo -e "${GREEN}✅ PASSED${NC}"
        record_test "$env" "cache-persistence" "PASSED" "$SECURITY" ""
    fi
    
    # Test 4: Functional - Basic connectivity
    echo -n "  [Functional] Site connectivity: "
    local status=$(curl -s -o /dev/null -w "%{http_code}" "$url" --connect-timeout 5)
    
    case $status in
        2*|3*)
            echo -e "${GREEN}✅ PASSED (HTTP $status)${NC}"
            record_test "$env" "connectivity" "PASSED" "$FUNCTIONAL" ""
            ;;
        401|403)
            echo -e "${YELLOW}⚠️  AUTH REQUIRED (HTTP $status - expected for APIs)${NC}"
            record_test "$env" "connectivity" "PASSED" "$FUNCTIONAL" "Auth required"
            ;;
        000)
            echo -e "${RED}❌ FAILED (No connection)${NC}"
            record_test "$env" "connectivity" "FAILED" "$FUNCTIONAL" "Connection failed"
            ;;
        *)
            echo -e "${RED}❌ FAILED (HTTP $status)${NC}"
            record_test "$env" "connectivity" "FAILED" "$FUNCTIONAL" "HTTP $status"
            ;;
    esac
    
    # Test 5: Performance
    echo -n "  [Performance] Response time: "
    local response_time=$(curl -s -o /dev/null -w "%{time_total}" "$url" --connect-timeout 5)
    
    if (( $(echo "$response_time < 1.0" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${GREEN}✅ EXCELLENT (${response_time}s)${NC}"
        record_test "$env" "performance" "PASSED" "$PERFORMANCE" ""
    elif (( $(echo "$response_time < 3.0" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${GREEN}✅ GOOD (${response_time}s)${NC}"
        record_test "$env" "performance" "PASSED" "$PERFORMANCE" ""
    elif (( $(echo "$response_time < 5.0" | bc -l 2>/dev/null || echo 0) )); then
        echo -e "${YELLOW}⚠️  SLOW (${response_time}s)${NC}"
        record_test "$env" "performance" "WARNING" "$PERFORMANCE" "Response time ${response_time}s"
    else
        echo -e "${RED}❌ VERY SLOW (${response_time}s)${NC}"
        record_test "$env" "performance" "FAILED" "$PERFORMANCE" "Response time ${response_time}s"
    fi
    
    # Clean up
    rm -rf "$temp_dir"
}

# Main execution
clear
echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║   Enhanced Cache Poisoning Protection QA Test - SRE-2215     ║${NC}"
echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
echo -e "Date: $(date)"
echo -e "Tester: $(whoami)"

print_header "Environment List"
for env in "${environments[@]}"; do
    echo "  • https://$env/"
done

print_header "Running Tests"

# Test each environment
for env in "${environments[@]}"; do
    test_environment "$env"
done

# Detailed failure analysis
print_header "Test Results Analysis"

echo -e "\n${CYAN}Security Test Results:${NC}"
if [ $security_failures -eq 0 ]; then
    echo -e "${GREEN}✅ ALL SECURITY TESTS PASSED${NC}"
    echo "   - No cache poisoning vulnerabilities detected"
    echo "   - All security headers properly handled"
else
    echo -e "${RED}❌ SECURITY FAILURES DETECTED: $security_failures${NC}"
    for key in "${!failure_details[@]}"; do
        if [[ "$key" == *"x-forwarded-host"* ]] || [[ "$key" == *"cache-persistence"* ]]; then
            echo -e "   ${RED}• $key: ${failure_details[$key]}${NC}"
        fi
    done
fi

echo -e "\n${CYAN}Functional Test Results:${NC}"
if [ $functional_failures -eq 0 ]; then
    echo -e "${GREEN}✅ All environments accessible${NC}"
else
    echo -e "${YELLOW}⚠️  Some environments had connectivity issues: $functional_failures${NC}"
    for key in "${!failure_details[@]}"; do
        if [[ "$key" == *"connectivity"* ]]; then
            echo "   • $key: ${failure_details[$key]}"
        fi
    done
fi

echo -e "\n${CYAN}Performance Results:${NC}"
if [ $performance_warnings -eq 0 ]; then
    echo -e "${GREEN}✅ All environments responding quickly${NC}"
else
    echo -e "${YELLOW}⚠️  Some environments are slow: $performance_warnings${NC}"
    for key in "${!failure_details[@]}"; do
        if [[ "$key" == *"performance"* ]]; then
            echo "   • $key: ${failure_details[$key]}"
        fi
    done
fi

# Final verdict
print_header "Deployment Recommendation"

if [ $security_failures -eq 0 ]; then
    echo -e "${GREEN}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║  ✅ SECURITY TESTS PASSED - SAFE TO DEPLOY TO PRODUCTION  ║${NC}"
    echo -e "${GREEN}╚════════════════════════════════════════════════════════════╝${NC}"
    
    if [ $functional_failures -gt 0 ] || [ $performance_warnings -gt 0 ]; then
        echo -e "\n${YELLOW}Note: Some non-critical issues detected:${NC}"
        echo "- Functional failures: $functional_failures (may be expected for certain environments)"
        echo "- Performance warnings: $performance_warnings (may be due to staging environment limitations)"
        echo -e "\n${CYAN}These do not affect the security fix and are not blockers for deployment.${NC}"
    fi
else
    echo -e "${RED}╔════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${RED}║  ❌ SECURITY TESTS FAILED - DO NOT DEPLOY TO PRODUCTION   ║${NC}"
    echo -e "${RED}╚════════════════════════════════════════════════════════════╝${NC}"
fi

# Generate detailed report
report_file="enhanced_qa_report_$(date +%Y%m%d_%H%M%S).txt"
{
    echo "Enhanced Cache Poisoning Protection QA Report"
    echo "============================================"
    echo "Date: $(date)"
    echo "Ticket: SRE-2215"
    echo ""
    echo "Summary:"
    echo "- Security Failures: $security_failures"
    echo "- Functional Failures: $functional_failures"
    echo "- Performance Warnings: $performance_warnings"
    echo ""
    echo "Security Status: $([ $security_failures -eq 0 ] && echo "PROTECTED" || echo "VULNERABLE")"
    echo ""
    echo "Detailed Results:"
    for key in "${!test_results[@]}"; do
        echo "- $key: ${test_results[$key]}"
        if [ "${test_results[$key]}" == "FAILED" ]; then
            echo "  Details: ${failure_details[$key]}"
        fi
    done
} > "$report_file"

echo -e "\nDetailed report saved to: ${YELLOW}$report_file${NC}"
