#!/usr/bin/env bash
set -e

echo "=========================================="
echo " Personal OS — Unified Test Suite Runner  "
echo "=========================================="

echo -e "\n[1/3] Running Backend Tests (pytest)..."
cd apps/api
python -m pytest tests/ -v --tb=short
cd ../..

echo -e "\n[2/3] Running Frontend Typecheck (tsc)..."
cd apps/web
npm run typecheck

echo -e "\n[3/3] Running Frontend Tests (vitest)..."
npm test
cd ../..

echo "=========================================="
echo " ALL TEST SUITES PASSED SUCCESSFULLY! (100%)"
echo "=========================================="
