import logging
import os

from flask import Flask
from flask_cors import CORS
from flask_executor import Executor
from flask_migrate import Migrate
from flask_sockets import Sockets
from flask_sqlalchemy import SQLAlchemy
from .version import __version__

# Default secret key used only for testing / development
DEFAULT_SECRET_KEY = "justasecretkeythatishouldputhere"

db = SQLAlchemy()
executor = Executor()
logging.getLogger().setLevel(logging.INFO)


def set_database_config(app, test_config=None, verbose=False):
    """Set configs to use SQL Alchemy library.

    Args:
        app: Flask application.
        test_config : Dictionary containing SQLAlchemy configs for test purposes.
        verbose : Level of flask application verbosity.
    Returns:
        app: Flask application.
    Raises:
        RuntimeError : If DATABASE_URL or test_config didn't initialized, RuntimeError exception will be raised.
    """
    db_url = os.environ.get("DATABASE_URL")
    migrate = Migrate(app, db)
    if test_config is None:
        if db_url:
            app.config.from_mapping(
                SQLALCHEMY_DATABASE_URI=db_url, SQLALCHEMY_TRACK_MODIFICATIONS=False
            )
        else:
            raise RuntimeError(
                "Invalid database address : Set DATABASE_URL environment var or add test_config parameter at create_app method."
            )
    else:
        app.config["SQLALCHEMY_DATABASE_URI"] = test_config["SQLALCHEMY_DATABASE_URI"]
        app.config["TESTING"] = (
            test_config["TESTING"] if test_config.get("TESTING") else True
        )
        app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = (
            test_config["SQLALCHEMY_TRACK_MODIFICATIONS"]
            if test_config.get("SQLALCHEMY_TRACK_MODIFICATIONS")
            else False
        )
    app.config["VERBOSE"] = verbose
    db.init_app(app)


def create_app(node_id: str, debug=False, n_replica=None, test_config=None) -> Flask:
    """Create flask application.

    Args:
         node_id: ID used to identify this node.
         debug: debug mode flag.
         n_replica: Number of model replicas used for fault tolerance purposes.
         test_config: database test settings.
    Returns:
         app : Flask App instance.
    """
    app = Flask(__name__)
    app.debug = debug

    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", None)

    if app.config["SECRET_KEY"] is None:
        app.config["SECRET_KEY"] = DEFAULT_SECRET_KEY
        logging.warning(
            "Using default secrect key, this is not safe and should be used only for testing and development. To define a secrete key please define the environment variable SECRET_KEY."
        )

    app.config["N_REPLICA"] = n_replica
    sockets = Sockets(app)

    from .main import main, model_centric, data_centric, ws, local_worker, auth, hook

    # Register app blueprints
    from .main import auth, hook, local_worker, main, ws

    # set_node_id(id)
    local_worker.id = node_id
    hook.local_worker._known_workers[node_id] = local_worker
    local_worker.add_worker(hook.local_worker)

    # Register app blueprints
    app.register_blueprint(main, url_prefix=r"/")
    app.register_blueprint(model_centric, url_prefix=r"/model_centric")
    app.register_blueprint(data_centric, url_prefix=r"/data_centric")

    sockets.register_blueprint(ws, url_prefix=r"/")

    # Set SQLAlchemy configs
    set_database_config(app, test_config=test_config)
    s = app.app_context().push()
    db.create_all()
    db.session.commit()

    # Set Authentication configs
    app = auth.set_auth_configs(app)

    CORS(app)

    # Threads
    executor.init_app(app)
    app.config["EXECUTOR_PROPAGATE_EXCEPTIONS"] = True
    app.config["EXECUTOR_TYPE"] = "thread"

    return app
