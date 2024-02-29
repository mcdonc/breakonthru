{ pkgs, lib, config, nixpkgs-python, ... }:

let
  pythonPackages = config.languages.python.package.pkgs;

  pythonsystemlibs = [
    pythonPackages.rpi-gpio
    # pythonPackages.gpiozero
    # pythonPackages.pyserial
    # pythonPackages.plaster-pastedeploy
    # pythonPackages.pyramid
    # pythonPackages.pyramid-chameleon
    # pythonPackages.waitress
    # pythonPackages.bcrypt
    # pythonPackages.websockets
    # pythonPackages.gpiozero
    # pythonPackages.pexpect
    # pythonPackages.setproctitle
    # pythonPackages.requests
    # pythonPackages.websocket-client
    # pythonPackages.supervisor
    # pythonPackages.pjsua2
  ];
in

{

  packages = with pkgs;
    [
      stdenv.cc.cc
      #git
    ] ++ pythonsystemlibs;

  process = {
    implementation = "process-compose";
    process-compose = {
      tui = "true";
      port = 9999;
    };
  };

  pre-commit.hooks = {
    ruff.enable = true;
    nixpkgs-fmt.enable = true;
  };

  process-managers.process-compose = {
    enable = true;
    settings = {
      log_location = "${config.env.DEVENV_STATE}/processes.log";
      log_configuration = {
        rotation = {
          max_size_mb = 10;
        };
        flush_each_line = true;
      };
    };
  };

  languages.python = {
    libraries = with pkgs; [
      zlib
    ];
    enable = true;
    version = "3.11.7";
    venv = {
      enable = true;
      requirements = "requirements.txt";
    };
  };

  processes.doorclient = {
    exec = ''
      $VIRTUAL_ENV/bin/doorclient ${config.env.DEVENV_ROOT}/dev/client.ini
    '';
    process-compose = {
      depends_on = { postgres = { condition = "process_healthy"; }; };
    };
  };

}
