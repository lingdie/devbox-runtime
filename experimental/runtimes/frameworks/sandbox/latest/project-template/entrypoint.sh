#!/bin/bash

app_env=${1:-development}

print_versions() {
    echo "Node.js: $(node --version)"
    echo "Bun: $(bun --version)"
    echo "Python: $(python3.14 --version)"
}

dev_commands() {
    echo "Running sandbox development environment..."
    print_versions
    NODE_ENV=development node server.js
}

prod_commands() {
    echo "Running sandbox production environment..."
    print_versions
    NODE_ENV=production node server.js
}

if [ "$app_env" = "production" ] || [ "$app_env" = "prod" ] ; then
    echo "Production environment detected"
    prod_commands
else
    echo "Development environment detected"
    dev_commands
fi
