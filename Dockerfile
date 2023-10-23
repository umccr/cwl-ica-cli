FROM docker.io/condaforge/mambaforge-pypy3:23.3.1-1

# Set args
ARG CONDA_GROUP_NAME="cwl_ica_group"
ARG CONDA_GROUP_ID=1000
ARG CONDA_USER_NAME="cwl_ica_user"
ARG CONDA_USER_ID=1000
ARG CONDA_ENV_NAME="cwl-ica"
ARG YQ_VERSION="v4.35.2"
ARG ICAV2_PLUGINS_CLI_VERSION="v2.15.1"

RUN export DEBIAN_FRONTEND=noninteractive && \
    echo "Updating Apt" 1>&2 && \
    apt-get update -y -q && \
    echo "Installing jq, nodejs, rsync, graphviz and parallel" 1>&2 && \
    apt-get install -y -q \
      jq \
      nodejs \
      rsync \
      graphviz \
      parallel \
      gcc \
      python3-dev \
      curl \
      build-essential \
      unzip && \
    echo "Cleaning up after apt installations" 1>&2 && \
    apt-get clean -y && \
    echo "Installing yq" 1>&2 && \
    wget --quiet \
      --output-document /usr/bin/yq \
      "https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64" && \
    chmod +x /usr/bin/yq && \
    echo "Installing gh binary" && \
    curl --fail --silent --show-error --location \
      "https://cli.github.com/packages/githubcli-archive-keyring.gpg" | \
    dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg && \
    chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | \
    tee /etc/apt/sources.list.d/github-cli.list > /dev/null && \
    apt-get update -y -q && \
    apt install gh -y -q && \
    echo "Installing aws cli" 1>&2 && \
    wget --quiet "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" \
      --output-document "awscliv2.zip" && \
    unzip -qq awscliv2.zip && \
    ./aws/install && \
    rm -rf aws/ awscliv2.zip && \
    echo "Updating conda" 1>&2 && \
    conda update --yes \
      --name base \
      --channel conda-forge \
      --channel defaults \
      conda && \
    echo "Updating mamba" 1>&2 && \
    mamba update --yes \
      --quiet \
      --name base \
      --channel conda-forge \
      --channel defaults \
      mamba && \
    echo "Cleaning conda" 1>&2 && \
    conda clean --all --yes --quiet && \
    echo "Cleaning mamba "1>&2 && \
    mamba clean --all --yes --quiet && \
    echo "Adding user groups" 1>&2 && \
    addgroup \
      --gid "${CONDA_GROUP_ID}" \
      "${CONDA_GROUP_NAME}" && \
    adduser \
      --disabled-password \
      --gid "${CONDA_GROUP_ID}" \
      --uid "${CONDA_USER_ID}" "${CONDA_USER_NAME}"


# Copy over source to . for user
COPY . "/cwl-ica-src-temp/"

RUN \
    cp -r "/cwl-ica-src-temp/." "/home/${CONDA_USER_NAME}/cwl-ica-src/" && \
    chown -R "${CONDA_USER_ID}:${CONDA_GROUP_ID}" "/home/${CONDA_USER_NAME}/cwl-ica-src/" && \
    rm -rf  "/cwl-ica-src-temp/"

# Switch to conda user
USER "${CONDA_USER_NAME}"
ENV USER="${CONDA_USER_NAME}"

# Add conda command
RUN echo "Adding in package and env paths to conda arc" 1>&2 && \
    conda config --append pkgs_dirs "\$HOME/.conda/pkgs" && \
    conda config --append envs_dirs "\$HOME/.conda/envs" && \
    echo "Installing into a conda env" 1>&2 && \
    ( \
      cd "/home/${CONDA_USER_NAME}" && \
      bash "cwl-ica-src/install.sh" -y -s && \
      rm -rf "cwl-ica-src/" \
    )

# Set environment variables for user
ENV CONDA_PREFIX="/home/${CONDA_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}"
ENV CONDA_DEFAULT_ENV="${CONDA_ENV_NAME}"

RUN ( \
      cd "/home/${CONDA_USER_NAME}" && \
      echo "Installing ICAv2 CLI Plugins" 1>&2 && \
      wget --quiet \
        --output-document "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
        "https://github.com/umccr/icav2-cli-plugins/releases/download/${ICAV2_PLUGINS_CLI_VERSION}/icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      echo "Got to here" 1>&2 && \
      unzip -qq "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" && \
      bash "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}/install.sh" "--no-autocompletion" && \
      rm -rf "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}" "icav2-plugins-cli--${ICAV2_PLUGINS_CLI_VERSION}.zip" \
    )

ENV PATH="/home/${CONDA_USER_NAME}/.conda/envs/${CONDA_ENV_NAME}/bin:${PATH}"
ENV ICAV2_CLI_PLUGINS_HOME="/home/${CONDA_USER_NAME}/.icav2-cli-plugins/"

CMD "cwl-ica"
