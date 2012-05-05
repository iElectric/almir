fabfile.py example (Fabric)
---------------------------

In the fabric directory you will find a fabfile.py. With 2 task: install_almir and remove_almir.

If you want to use the fabric right away, you can run::

        cd fabric
        python bootstrap.py
        bin/buildout

This will create a "virtualenv" for you.
To view available task run::

        bin/fab -l

Installing almir
****************

You need to configure the fabfile.py file:

.. include:: ../../fabric/fabfile.py
        :literal:
        :start-after: doctag-settings-start
        :end-before: doctag-settings-end

.. note::
        You don't need to set env.host_string.
        If you don't set it, fabric will ask you where do you want to install almir.

.. warning::
        This fabfile only works in Ubuntu. And was tested only in **Ubuntu 10.04 LTS** with the **postgresql** configuration.
        Please use with care.

After you have configured the fabfile.py. Run::

        bin/fab install_almir


Removing almir
**************

If you want to remove almir. Run::

        bin/fab remove_almir

.. warning::
        This will **remove the user** (env.almir_user) and **delete his home**!!!
