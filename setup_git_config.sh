#!/bin/bash

# Function to setup git config
setup_git() {
    local var_name="$1"
    local config_key="$2"
    local display_name="$3"
    local value="${!var_name}"
    
    if [ -n "$value" ]; then
        echo "Setting Git $display_name: $value"
        git config --global "$config_key" "$value"
    else
        echo "Git $display_name variable ($var_name) not defined, skipping"
    fi
}

# Process name and email
setup_git "GIT_USER_NAME" "user.name" "User Name"
setup_git "GIT_USER_EMAIL" "user.email" "User Email"

echo "Git configuration completed"
