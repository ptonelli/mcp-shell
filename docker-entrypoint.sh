#!/bin/bash

# docker-entrypoint.sh

# Use default UID/GID 1000 if not specified
USER_ID=${UID:-1000}
GROUP_ID=${GID:-1000}

echo "Starting with UID: $USER_ID, GID: $GROUP_ID"

# Create the group if it doesn't exist
if ! getent group $GROUP_ID > /dev/null; then
    groupadd -g $GROUP_ID mcp
fi

# Create the user if it doesn't exist
if ! getent passwd $USER_ID > /dev/null; then
    useradd -u $USER_ID -g $GROUP_ID -m -s /bin/bash mcp
fi

# Ensure home directory is owned by the user (especially if it existed before)
chown $USER_ID:$GROUP_ID /home/mcp

# Set up SSH keys from environment variables
if [ -f /usr/local/bin/setup_ssh_keys.sh ]; then
    echo "Setting up SSH keys from environment variables..."
    SSH_DIR=/home/mcp/.ssh
    mkdir -p $SSH_DIR
    chown -R $USER_ID:$GROUP_ID "$SSH_DIR"
    chmod 700 "$SSH_DIR"
    gosu $USER_ID:$GROUP_ID /usr/local/bin/setup_ssh_keys.sh
fi

# Set up Git configuration from environment variables
if [ -f /usr/local/bin/setup_git_config.sh ]; then
    echo "Setting up Git configuration from environment variables..."
    gosu $USER_ID:$GROUP_ID /usr/local/bin/setup_git_config.sh
fi

# Create default project directory if it doesn't exist
if [ ! -d "$WORKDIR/default" ]; then
    mkdir -p $WORKDIR/default
    chown -R $USER_ID:$GROUP_ID $WORKDIR
else
    # Check if we have write permissions to the directory
    if [ ! -w "$WORKDIR/default" ]; then
        echo "WARNING: The directory $WORKDIR/default exists but does not have write permissions. Operations requiring write access may fail."
    fi
fi

# Run the original command as the specified user
exec gosu $USER_ID:$GROUP_ID "$@"
