import logging
from typing import List, Dict, Any, Optional, Union
import datetime
import time
from langchain_core.tools import Tool

class ZabbixDataHandler:
    @staticmethod
    def paginate_response(
        data: List[Dict], 
        page: int = 1, 
        page_size: int = 50, 
        formatter: Optional[callable] = None
    ) -> Dict[str, Union[str, int]]:
        """
        Paginate large datasets with intelligent formatting.
        """
        total_items = len(data)
        total_pages = (total_items + page_size - 1) // page_size
        
        start_index = (page - 1) * page_size
        end_index = start_index + page_size
        
        paginated_data = data[start_index:end_index]
        
        # Use default or custom formatter
        if formatter:
            formatted_content = formatter(paginated_data)
        else:
            formatted_content = "\n".join(str(item) for item in paginated_data)
        
        return {
            "content": formatted_content,
            "total_items": total_items,
            "total_pages": total_pages,
            "current_page": page,
            "page_size": page_size
        }

class ZabbixToolFunctions:
    def __init__(self, zabbix_client):
        """
        Initialize Zabbix tool functions with a Zabbix API client.
        """
        self.zabbix = zabbix_client
        self.logger = logging.getLogger(__name__)

    def get_hosts(self, page: int = 1, page_size: int = 50, include_details: bool = True) -> str:
        """
        Retrieve hosts with advanced pagination and formatting.
        """
        try:
            output_fields = ["hostid", "name", "status"]
            if include_details:
                output_fields.extend(["host", "description"])
            
            hosts = self.zabbix.host.get(output=output_fields)
            return self._paginate_and_format(hosts, page, page_size, self._host_formatter, include_details)

        except Exception as e:
            self.logger.error(f"Error retrieving hosts: {e}")
            return f"Error retrieving hosts: {str(e)}"

    def _host_formatter(self, host_list, include_details):
        formatted_hosts = []
        for host in host_list:
            status = "Enabled" if host['status'] == '0' else "Disabled"
            host_info = f"Host: {host['name']} (ID: {host['hostid']}, Status: {status})"
            if include_details:
                host_info += f"\n  Hostname: {host.get('host', 'N/A')}\n  Description: {host.get('description', 'No description')}"
            formatted_hosts.append(host_info)
        return "\n\n".join(formatted_hosts)

    def _paginate_and_format(self, data, page, page_size, formatter, *formatter_args):
        result = ZabbixDataHandler.paginate_response(data, page, page_size, lambda x: formatter(x, *formatter_args))
        response = result['content']
        response += f"\n\nPage {result['current_page']} of {result['total_pages']} (Total Items: {result['total_items']})"
        return response

    def get_items(self, host_id: Optional[str] = None) -> str:
        """
        Retrieve items associated with a specific host ID.
        """
        try:
            item_params = {
                "output": ["itemid", "name", "key_", "lastvalue"],
                "sortfield": "name"
            }
            if host_id:
                item_params["hostids"] = host_id

            items = self.zabbix.item.get(**item_params)
            if not items:
                return "No items found."

            return "\n".join(
                f"Item ID: {item['itemid']}, Name: {item['name']}, Key: {item['key_']}, Last Value: {item.get('lastvalue', 'N/A')}"
                for item in items
            )

        except Exception as e:
            self.logger.error(f"Error retrieving items: {e}")
            return f"Error retrieving items: {str(e)}"

    def _item_formatter(self, item_list):
        formatted_items = []
        for item in item_list:
            value_type_map = {
                '0': 'Numeric (float)',
                '1': 'Character',
                '2': 'Log',
                '3': 'Numeric (unsigned)',
                '4': 'Text'
            }
            item_info = (
                f"Item: {item['name']}\n"
                f"  ID: {item['itemid']}\n"
                f"  Key: {item['key_']}\n"
                f"  Type: {item['type']}\n"
                f"  Value Type: {value_type_map.get(item['value_type'], 'Unknown')}\n"
                f"  Last Value: {item.get('lastvalue', 'N/A')}\n"
                f"  Units: {item.get('units', 'N/A')}\n"
                f"  Status: {'Enabled' if item['status'] == '0' else 'Disabled'}"
            )
            if item.get('error'):
                item_info += f"\n  Error: {item['error']}"
            formatted_items.append(item_info)
        return "\n\n".join(formatted_items)

    def get_triggers(self, page: int = 1, page_size: int = 50, severity_filter: Optional[List[str]] = None) -> str:
        try:
            trigger_params = {
                "output": ["triggerid", "description", "priority", "status", "lastchange", "value"],
                "sortfield": "lastchange",
                "sortorder": "DESC"
            }
            if severity_filter:
                severity_map = {
                    "not_classified": 0,
                    "information": 1,
                    "warning": 2,
                    "average": 3,
                    "high": 4,
                    "disaster": 5
                }
                trigger_params["filter"] = {
                    "priority": [severity_map.get(sev.lower(), sev) for sev in severity_filter]
                }

            triggers = self.zabbix.trigger.get(**trigger_params)
            return self._paginate_and_format(triggers, page, page_size, self._trigger_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving triggers: {e}")
            return f"Error retrieving triggers: {str(e)}"

    def _trigger_formatter(self, trigger_list):
        formatted_triggers = []
        for trigger in trigger_list:
            priority_map = {
                0: "Not Classified",
                1: "Information",
                2: "Warning",
                3: "Average",
                4: "High",
                5: "Disaster"
            }
            priority = priority_map.get(int(trigger['priority']), "Unknown")
            status = "Enabled" if trigger['status'] == '0' else "Disabled"
            value = "Problem" if trigger['value'] == '1' else "OK"
            trigger_info = [
                f"Trigger: {trigger['description']}",
                f"  ID: {trigger['triggerid']}",
                f"  Priority: {priority}",
                f"  Status: {status}",
                f"  Current State: {value}"
            ]
            if trigger.get('lastchange'):
                timestamp = datetime.datetime.fromtimestamp(int(trigger['lastchange'])).strftime('%Y-%m-%d %H:%M:%S')
                trigger_info.append(f"  Last Changed: {timestamp}")
            formatted_triggers.append("\n".join(trigger_info))
        return "\n\n".join(formatted_triggers)

    def get_host_status(self, page: int = 1, page_size: int = 50, status_filter: Optional[str] = None) -> str:
        try:
            host_params = {
                "output": ["hostid", "name", "status"],
                "sortfield": "name"
            }
            if status_filter:
                status_map = {
                    "enabled": "0",
                    "disabled": "1"
                }
                host_params["filter"] = {
                    "status": status_map.get(status_filter.lower(), status_filter)
                }

            hosts = self.zabbix.host.get(**host_params)
            return self._paginate_and_format(hosts, page, page_size, self._host_status_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving host statuses: {e}")
            return f"Error retrieving host statuses: {str(e)}"

    def _host_status_formatter(self, host_list):
        formatted_statuses = []
        for host in host_list:
            status = "Enabled" if host['status'] == '0' else "Disabled"
            status_info = f"Host: {host['name']} (ID: {host['hostid']}) - Status: {status}"
            formatted_statuses.append(status_info)
        return "\n".join(formatted_statuses)

    def get_events(self, page: int = 1, page_size: int = 50, event_type: Optional[str] = None, time_from: Optional[int] = None, time_till: Optional[int] = None) -> str:
        try:
            event_params = {
                "output": ["eventid", "source", "object", "objectid", "clock", "value", "acknowledged", "severity"],
                "sortfield": "clock",
                "sortorder": "DESC"
            }
            source_map = {
                "trigger": 0,
                "discovery": 1,
                "auto_registration": 2,
                "internal": 3
            }
            if event_type:
                event_params["filter"] = {
                    "source": source_map.get(event_type.lower(), event_type)
                }
            if time_from:
                event_params["time_from"] = time_from
            if time_till:
                event_params["time_till"] = time_till
            
            events = self.zabbix.event.get(**event_params)
            return self._paginate_and_format(events, page, page_size, self._events_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving events: {e}")
            return f"Error retrieving events: {str(e)}"

    def _events_formatter(self, event_list):
        formatted_events = []
        for event in event_list:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(event['clock'])))
            formatted_events.append(
                f"Event ID: {event['eventid']}\n"
                f"  Source: {event.get('source', 'Unknown')}\n"
                f"  Timestamp: {timestamp}\n"
                f"  Severity: {event.get('severity', 'Unknown')}\n"
                f"  Acknowledged: {'Yes' if event['acknowledged'] == '1' else 'No'}\n"
                f"  Object ID: {event['objectid']}"
            )
        return "\n\n".join(formatted_events)

    def get_item_values(self, host_id: Optional[str] = None, item_key: Optional[str] = None, page: int = 1, page_size: int = 50) -> str:
        try:
            item_params = {
                "output": ["itemid", "name", "key_", "lastvalue", "lastclock", "value_type", "units"],
                "sortfield": "name"
            }
            if host_id:
                item_params["hostids"] = host_id
            if item_key:
                item_params["filter"] = {"key_": item_key}

            items = self.zabbix.item.get(**item_params)
            return self._paginate_and_format(items, page, page_size, self._item_values_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving item values: {e}")
            return f"Error retrieving item values: {str(e)}"

    def _item_values_formatter(self, item_list):
        formatted_values = []
        for item in item_list:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(item.get('lastclock', 0))))
            formatted_values.append(
                f"Item: {item['name']}\n"
                f"  Key: {item['key_']}\n"
                f"  Last Value: {item.get('lastvalue', 'N/A')}\n"
                f"  Units: {item.get('units', 'N/A')}\n"
                f"  Last Updated: {timestamp}\n"
                f"  Status: {'Enabled' if item['status'] == '0' else 'Disabled'}"
            )
        return "\n\n".join(formatted_values)

    def get_host_inventory(self, host_id: Optional[str] = None, inventory_fields: Optional[List[str]] = None, page: int = 1, page_size: int = 50) -> str:
        try:
            inventory_params = {
                "output": ["hostid", "name", "inventory_mode", "inventory"],
                "selectInventory": "extend"
            }
            if host_id:
                inventory_params["hostids"] = host_id
            
            hosts = self.zabbix.host.get(**inventory_params)
            return self._paginate_and_format(hosts, page, page_size, self._host_inventory_formatter, inventory_fields)

        except Exception as e:
            self.logger.error(f"Error retrieving host inventory: {e}")
            return f"Error retrieving host inventory: {str(e)}"

    def _host_inventory_formatter(self, host_list, inventory_fields):
        formatted_inventories = []
        for host in host_list:
            inventory_info = f"Host: {host['name']} (ID: {host['hostid']})\n"
            inventory_info += f"  Inventory Mode: {host.get('inventory_mode', 'Unknown')}"
            if inventory_fields:
                inventory_info += "\n  Inventory Details:"
                for field in inventory_fields:
                    if field in host['inventory']:
                        inventory_info += f"\n    {field.replace('_', ' ').title()}: {host['inventory'][field]}"
            formatted_inventories.append(inventory_info)
        return "\n\n".join(formatted_inventories)

    def get_host_alerts(self, host_id: Optional[str] = None, severity: Optional[str] = None, page: int = 1, page_size: int = 50) -> str:
        try:
            alert_params = {
                "output": ["alertid", "triggerid", "clock", "value", "severity", "status"],
                "sortfield": "clock",
                "sortorder": "DESC"
            }
            if host_id:
                alert_params["hostids"] = host_id
            if severity:
                severity_map = {
                    "not_classified": 0,
                    "information": 1,
                    "warning": 2,
                    "average": 3,
                    "high": 4,
                    "disaster": 5
                }
                alert_params["filter"] = {
                    "severity": severity_map.get(severity.lower(), severity)
                }
            alerts = self.zabbix.trigger.get(**alert_params)
            return self._paginate_and_format(alerts, page, page_size, self._alerts_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving host alerts: {e}")
            return f"Error retrieving host alerts: {str(e)}"

    def _alerts_formatter(self, alert_list):
        formatted_alerts = []
        for alert in alert_list:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(alert['clock'])))
            formatted_alerts.append(
                f"Alert ID: {alert['alertid']}\n"
                f"  Trigger ID: {alert['triggerid']}\n"
                f"  Timestamp: {timestamp}\n"
                f"  Severity: {alert.get('severity', 'Unknown')}\n"
                f"  Status: {'OK' if alert['value'] == '0' else 'Problem'}"
            )
        return "\n\n".join(formatted_alerts)

    def get_application_items(self, page: int = 1, page_size: int = 50, host_id: Optional[str] = None) -> str:
        try:
            app_items_params = {
                "output": ["itemid", "name", "key_", "value_type", "units", "lastvalue"],
                "sortfield": "name"
            }
            if host_id:
                app_items_params["hostids"] = host_id
            
            items = self.zabbix.item.get(**app_items_params)
            return self._paginate_and_format(items, page, page_size, self._application_items_formatter)

        except Exception as e:
            self.logger.error(f"Error retrieving application items: {e}")
            return f"Error retrieving application items: {str(e)}"

    def _application_items_formatter(self, item_list):
        formatted_items = []
        for item in item_list:
            value_type_map = {
                '0': 'Numeric (float)',
                '1': 'Character',
                '2': 'Log',
                '3': 'Numeric (unsigned)',
                '4': 'Text'
            }
            item_info = (
                f"Item: {item['name']}\n"
                f"  ID: {item['itemid']}\n"
                f"  Key: {item['key_']}\n"
                f"  Value Type: {value_type_map.get(item['value_type'], 'Unknown')}\n"
                f"  Last Value: {item.get('lastvalue', 'N/A')}\n"
                f"  Units: {item.get('units', 'N/A')}"
            )
            formatted_items.append(item_info)
        return "\n\n".join(formatted_items)

    def get_alert_history(self, limit: int = 50) -> str:
        """
        Retrieve recent alert history.
        """
        try:
            alerts = self.zabbix.alert.get(limit=limit, output=["alertid", "clock", "message", "severity", "eventid"])
            
            def alert_formatter(alert_list):
                formatted_alerts = []
                for alert in alert_list:
                    timestamp = datetime.datetime.fromtimestamp(int(alert['clock'])).strftime('%Y-%m-%d %H:%M:%S')
                    severity_map = {
                        '0': 'Not classified',
                        '1': 'Information',
                        '2': 'Warning',
                        '3': 'Average',
                        '4': 'High',
                        '5': 'Disaster'
                    }
                    severity = severity_map.get(alert.get('severity', ''), 'Unknown')
                    formatted_alerts.append(
                        f"Alert ID: {alert['alertid']}\n  Time: {timestamp}\n  Severity: {severity}\n  Message: {alert['message']}"
                    )
                return "\n\n".join(formatted_alerts)
            
            response = alert_formatter(alerts)
            response += f"\n\nRetrieved {len(alerts)} alerts"
            return response
        
        except Exception as e:
            self.logger.error(f"Error retrieving alert history: {e}")
            return f"Error retrieving alert history: {str(e)}"

    def get_system_performance(self) -> str:
        """
        Retrieve system performance metrics.
        """
        try:
            performance = self.zabbix.item.get(search={"key_": "system"}, output=["itemid", "name", "lastvalue"])
            formatted_performance = "\n".join(
                f"{item['name']}: {item.get('lastvalue', 'N/A')}" for item in performance
            )
            return f"System Performance Metrics:\n{formatted_performance}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving system performance: {e}")
            return f"Error retrieving system performance: {str(e)}"

    def get_trigger_performance(self, limit: int = 50) -> str:
        """
        Retrieve performance data for triggers.
        """
        try:
            triggers = self.zabbix.trigger.get(limit=limit, output=["triggerid", "description", "priority", "value"])
            priority_map = {
                '0': 'Not classified',
                '1': 'Information',
                '2': 'Warning',
                '3': 'Average',
                '4': 'High',
                '5': 'Disaster'
            }
            formatted_triggers = "\n".join(
                f"Trigger ID: {trigger['triggerid']}\n  Description: {trigger['description']}\n  Priority: {priority_map.get(trigger['priority'], 'Unknown')}\n  Status: {'Active' if trigger['value'] == '1' else 'Inactive'}"
                for trigger in triggers
            )
            return f"Trigger Performance:\n{formatted_triggers}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving trigger performance: {e}")
            return f"Error retrieving trigger performance: {str(e)}"

    def get_graph_data(self, graph_id: str) -> str:
        """
        Retrieve graph data for a given graph ID.
        """
        try:
            graph = self.zabbix.graph.get(graphids=graph_id, output=["graphid", "name", "width", "height"])
            if graph:
                graph_info = graph[0]
                return f"Graph ID: {graph_info['graphid']}\n  Name: {graph_info['name']}\n  Dimensions: {graph_info['width']}x{graph_info['height']}"
            else:
                return f"No graph found for Graph ID: {graph_id}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving graph data: {e}")
            return f"Error retrieving graph data: {str(e)}"

    def get_trend_data(self, item_id: str, time_from: int, time_to: int) -> str:
        """
        Retrieve trend data for a given item ID.
        """
        try:
            trends = self.zabbix.trend.get(itemids=item_id, time_from=time_from, time_to=time_to, output=["itemid", "value_avg", "value_min", "value_max", "clock"])
            formatted_trends = "\n".join(
                f"Time: {datetime.datetime.fromtimestamp(int(trend['clock'])).strftime('%Y-%m-%d %H:%M:%S')}\n  Avg: {trend['value_avg']}\n  Min: {trend['value_min']}\n  Max: {trend['value_max']}"
                for trend in trends
            )
            return f"Trend Data for Item {item_id}:\n{formatted_trends}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving trend data: {e}")
            return f"Error retrieving trend data: {str(e)}"

    def get_metrics_by_host(self, host_id: str) -> str:
        """
        Retrieve metrics for a specific host.
        """
        try:
            metrics = self.zabbix.item.get(hostids=host_id, output=["itemid", "name", "key_", "lastvalue"])
            if not metrics:
                return f"No metrics found for Host ID: {host_id}"
            
            formatted_metrics = "\n".join(
                f"Metric ID: {metric['itemid']}\n  Name: {metric['name']}\n  Key: {metric['key_']}\n  Last Value: {metric.get('lastvalue', 'N/A')}"
                for metric in metrics
            )
            return f"Metrics for Host {host_id}:\n{formatted_metrics}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving metrics for host {host_id}: {e}")
            return f"Error retrieving metrics for host {host_id}: {str(e)}"

    def get_zabbix_performance_data(self) -> str:
        """
        Retrieve Zabbix server performance data.
        """
        try:
            performance = self.zabbix.item.get(search={"key_": "zabbix[performance]"}, output=["itemid", "name", "lastvalue"])
            if not performance:
                return "No Zabbix performance data found."
            
            formatted_performance = "\n".join(
                f"{item['name']}: {item.get('lastvalue', 'N/A')}" for item in performance
            )
            return f"Zabbix Performance Data:\n{formatted_performance}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving Zabbix performance data: {e}")
            return f"Error retrieving Zabbix performance data: {str(e)}"

    def get_db_performance(self) -> str:
        """
        Retrieve database performance metrics.
        """
        try:
            db_metrics = self.zabbix.item.get(search={"key_": "db.performance"}, output=["itemid", "name", "lastvalue"])
            if not db_metrics:
                return "No database performance data found."
            
            formatted_metrics = "\n".join(
                f"{item['name']}: {item.get('lastvalue', 'N/A')}" for item in db_metrics
            )
            return f"Database Performance Metrics:\n{formatted_metrics}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving database performance metrics: {e}")
            return f"Error retrieving database performance metrics: {str(e)}"

    def get_network_performance(self) -> str:
        """
        Retrieve network performance data.
        """
        try:
            network_metrics = self.zabbix.item.get(search={"key_": "net.if"}, output=["itemid", "name", "lastvalue"])
            if not network_metrics:
                return "No network performance data found."
            
            formatted_metrics = "\n".join(
                f"{item['name']}: {item.get('lastvalue', 'N/A')}" for item in network_metrics
            )
            return f"Network Performance Data:\n{formatted_metrics}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving network performance data: {e}")
            return f"Error retrieving network performance data: {str(e)}"

    def get_proxy_performance(self) -> str:
        """
        Retrieve Zabbix proxy performance data.
        """
        try:
            proxy_metrics = self.zabbix.item.get(search={"key_": "zabbix[proxy]"}, output=["itemid", "name", "lastvalue"])
            if not proxy_metrics:
                return "No proxy performance data found."
            
            formatted_metrics = "\n".join(
                f"{item['name']}: {item.get('lastvalue', 'N/A')}" for item in proxy_metrics
            )
            return f"Proxy Performance Data:\n{formatted_metrics}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving proxy performance data: {e}")
            return f"Error retrieving proxy performance data: {str(e)}"

    def get_sla_data(self, sla_id: str) -> str:
        """
        Retrieve SLA data for a given SLA ID.
        """
        try:
            sla = self.zabbix.service.get(serviceids=sla_id, selectSLA=["id", "name", "sla", "timeperiods"])
            if not sla:
                return f"No SLA data found for SLA ID: {sla_id}"
            
            sla_info = sla[0]
            formatted_sla = (
                f"SLA ID: {sla_info['id']}\n"
                f"Name: {sla_info['name']}\n"
                f"SLA: {sla_info['sla']}\n"
                f"Time Periods: {', '.join(tp['period'] for tp in sla_info.get('timeperiods', []))}"
            )
            return f"SLA Data:\n{formatted_sla}"
        
        except Exception as e:
            self.logger.error(f"Error retrieving SLA data for SLA ID {sla_id}: {e}")
            return f"Error retrieving SLA data for SLA ID {sla_id}: {str(e)}"
        
    def get_users(self) -> str:
        """
        Retrieve a list of users from Zabbix.
        """
        try:
            user_params = [
                {"output": ["userid", "username", "name", "surname"]},
                {"output": ["userid", "alias", "name", "surname"]},
                {"output": ["userid", "username"]},
                {"output": ["userid", "alias"]},
                {"output": "extend"}  # Most flexible option
            ]
            
            for params in user_params:
                try:
                    users = self.zabbix.user.get(**params)
                    
                    if users:
                        formatted_users = []
                        for user in users:
                            username = user.get('username', user.get('alias', 'N/A'))
                            user_info = f"User ID: {user.get('userid', 'N/A')}\n  Username: {username}"
                            if user.get('name') or user.get('surname'):
                                full_name = f"{user.get('name', '')} {user.get('surname', '')}".strip()
                                user_info += f"\n  Name: {full_name}"
                            formatted_users.append(user_info)

                        return f"Users in Zabbix:\n" + "\n\n".join(formatted_users)
                
                except Exception as inner_e:
                    logging.warning(f"User retrieval attempt failed: {inner_e}")
                    continue
            
            return "No users could be retrieved from Zabbix. Please check your API configuration."
        
        except Exception as e:
            logging.error(f"Comprehensive error retrieving users: {e}")
            return f"Error retrieving users: {str(e)}"

    def get_user_groups(self) -> str:
        """
        Retrieve user groups from Zabbix.
        """
        try:
            groups = self.zabbix.usergroup.get(output=["usrgrpid", "name"])
            if not groups:
                return "No user groups found in Zabbix."

            formatted_groups = "\n".join(
                f"Group ID: {group['usrgrpid']}\n  Name: {group['name']}" for group in groups
            )
            return f"User Groups in Zabbix:\n{formatted_groups}"

        except Exception as e:
            self.logger.error(f"Error retrieving user groups: {e}")
            return f"Error retrieving user groups: {str(e)}"

    def get_user_roles(self) -> str:
        """
        Retrieve user roles from Zabbix.
        """
        try:
            roles = self.zabbix.role.get(output=["roleid", "name"])
            if not roles:
                return "No user roles found in Zabbix."

            formatted_roles = "\n".join(
                f"Role ID: {role['roleid']}\n  Name: {role['name']}" for role in roles
            )
            return f"User Roles in Zabbix:\n{formatted_roles}"

        except Exception as e:
            self.logger.error(f"Error retrieving user roles: {e}")
            return f"Error retrieving user roles: {str(e)}"

    def get_custom_item(self, key: str) -> str:
        """
        Retrieve a custom item by its key.
        """
        try:
            items = self.zabbix.item.get(search={"key_": key}, output=["itemid", "name", "lastvalue"])
            if not items:
                return f"No items found with key: {key}"

            formatted_items = "\n".join(
                f"Item ID: {item['itemid']}\n  Name: {item['name']}\n  Last Value: {item.get('lastvalue', 'N/A')}"
                for item in items
            )
            return f"Custom Items with key '{key}':\n{formatted_items}"

        except Exception as e:
            self.logger.error(f"Error retrieving custom item for key '{key}': {e}")
            return f"Error retrieving custom item for key '{key}': {str(e)}"

    def get_items_by_host_group(self, group_id: str) -> str:
        """
        Retrieve items by host group ID.
        """
        try:
            hosts = self.zabbix.host.get(groupids=group_id, output=["hostid", "name"])
            if not hosts:
                return f"No hosts found for group ID: {group_id}"

            items = []
            for host in hosts:
                host_items = self.zabbix.item.get(hostids=host['hostid'], output=["itemid", "name", "key_", "lastvalue"])
                items.extend(
                    f"Host: {host['name']} (Host ID: {host['hostid']})\n  Item ID: {item['itemid']}\n  Name: {item['name']}\n  Key: {item['key_']}\n  Last Value: {item.get('lastvalue', 'N/A')}"
                    for item in host_items
                )

            return f"Items in Host Group {group_id}:\n" + "\n\n".join(items)

        except Exception as e:
            self.logger.error(f"Error retrieving items by host group {group_id}: {e}")
            return f"Error retrieving items by host group {group_id}: {str(e)}"

    def get_host_by_name(self, name: str) -> str:
        """
        Retrieve a host by its name.
        """
        try:
            hosts = self.zabbix.host.get(filter={"name": name}, output=["hostid", "name", "status"])
            if not hosts:
                return f"No hosts found with name: {name}"

            formatted_hosts = "\n".join(
                f"Host ID: {host['hostid']}, Name: {host['name']}, Status: {'Enabled' if host['status'] == '0' else 'Disabled'}"
                for host in hosts
            )
            return f"Host(s) with name '{name}':\n{formatted_hosts}"

        except Exception as e:
            return f"Error retrieving host by name '{name}': {str(e)}"

    def get_trigger_by_expression(self, expression: str) -> str:
        """
        Retrieve a trigger by its expression.
        """
        try:
            triggers = self.zabbix.trigger.get(filter={"expression": expression}, output=["triggerid", "description", "status"])
            if not triggers:
                return f"No triggers found with expression: {expression}"

            formatted_triggers = "\n".join(
                f"Trigger ID: {trigger['triggerid']}\n  Description: {trigger['description']}\n  Status: {'Enabled' if trigger['status'] == '0' else 'Disabled'}"
                for trigger in triggers
            )
            return f"Trigger(s) with expression '{expression}':\n{formatted_triggers}"

        except Exception as e:
            self.logger.error(f"Error retrieving trigger by expression '{expression}': {e}")
            return f"Error retrieving trigger by expression '{expression}': {str(e)}"

    def get_dependencies_by_trigger(self, trigger_id: str) -> str:
        """
        Retrieve dependencies for a given trigger.
        """
        try:
            dependencies = self.zabbix.trigger.get(
                triggerids=trigger_id, 
                selectDependencies=["triggerid", "description"]
            )
            if not dependencies:
                return f"No dependencies found for trigger ID: {trigger_id}"

            formatted_dependencies = "\n".join(
                f"Dependency Trigger ID: {dep['triggerid']}\n  Description: {dep['description']}"
                for dep in dependencies[0].get("dependencies", [])
            )
            return f"Dependencies for Trigger ID {trigger_id}:\n{formatted_dependencies}"

        except Exception as e:
            self.logger.error(f"Error retrieving dependencies for trigger ID '{trigger_id}': {e}")
            return f"Error retrieving dependencies for trigger ID '{trigger_id}': {str(e)}"

    def get_screens(self) -> str:
        """
        Retrieve all screens from Zabbix.
        """
        try:
            screens = self.zabbix.screen.get(output=["screenid", "name"])
            if not screens:
                return "No screens found in Zabbix."

            formatted_screens = "\n".join(
                f"Screen ID: {screen['screenid']}\n  Name: {screen['name']}" for screen in screens
            )
            return f"Screens in Zabbix:\n{formatted_screens}"

        except Exception as e:
            self.logger.error(f"Error retrieving screens: {e}")
            return f"Error retrieving screens: {str(e)}"

    def get_graphs_by_host(self, host_id: str) -> str:
        """
        Retrieve graphs for a given host.
        """
        try:
            graphs = self.zabbix.graph.get(hostids=host_id, output=["graphid", "name"])
            if not graphs:
                return f"No graphs found for host ID: {host_id}"

            formatted_graphs = "\n".join(
                f"Graph ID: {graph['graphid']}\n  Name: {graph['name']}" for graph in graphs
            )
            return f"Graphs for Host ID {host_id}:\n{formatted_graphs}"

        except Exception as e:
            self.logger.error(f"Error retrieving graphs for host ID '{host_id}': {e}")
            return f"Error retrieving graphs for host ID '{host_id}': {str(e)}"

    def get_zabbix_api_limits(self) -> str:
        """
        Retrieve Zabbix API limits.
        """
        try:
            limits = self.zabbix.apiinfo.version()
            return f"Zabbix API version: {limits}"

        except Exception as e:
            self.logger.error(f"Error retrieving Zabbix API limits: {e}")
            return f"Error retrieving Zabbix API limits: {str(e)}"

    def get_scheduled_tasks(self) -> str:
        """
        Retrieve scheduled tasks from Zabbix.
        """
        try:
            tasks = self.zabbix.task.get(output=["taskid", "name", "status", "type"])
            if not tasks:
                return "No scheduled tasks found in Zabbix."

            formatted_tasks = "\n".join(
                f"Task ID: {task['taskid']}\n  Name: {task['name']}\n  Status: {'Completed' if task['status'] == '1' else 'Pending'}\n  Type: {task['type']}"
                for task in tasks
            )
            return f"Scheduled Tasks in Zabbix:\n{formatted_tasks}"

        except Exception as e:
            self.logger.error(f"Error retrieving scheduled tasks: {e}")
            return f"Error retrieving scheduled tasks: {str(e)}"

    def get_host_maintenance(self, host_id: str) -> str:
        """
        Retrieve maintenance details for a given host.
        """
        try:
            maintenances = self.zabbix.maintenance.get(
                hostids=host_id, 
                output=["maintenanceid", "name", "active_since", "active_till"]
            )
            if not maintenances:
                return f"No maintenance found for host ID: {host_id}"

            formatted_maintenances = "\n".join(
                f"Maintenance ID: {maintenance['maintenanceid']}\n  Name: {maintenance['name']}\n  Active Since: {maintenance['active_since']}\n  Active Till: {maintenance['active_till']}"
                for maintenance in maintenances
            )
            return f"Maintenance for Host ID {host_id}:\n{formatted_maintenances}"

        except Exception as e:
            self.logger.error(f"Error retrieving maintenance for host ID '{host_id}': {e}")
            return f"Error retrieving maintenance for host ID '{host_id}': {str(e)}"

    def get_maintenance_periods(self) -> str:
        """
        Retrieve all maintenance periods from Zabbix.
        """
        try:
            maintenances = self.zabbix.maintenance.get(output=["maintenanceid", "name", "active_since", "active_till"])
            if not maintenances:
                return "No maintenance periods found in Zabbix."

            formatted_maintenances = "\n".join(
                f"Maintenance ID: {maintenance['maintenanceid']}\n  Name: {maintenance['name']}\n  Active Since: {maintenance['active_since']}\n  Active Till: {maintenance['active_till']}"
                for maintenance in maintenances
            )
            return f"Maintenance Periods in Zabbix:\n{formatted_maintenances}"

        except Exception as e:
            self.logger.error(f"Error retrieving maintenance periods: {e}")
            return f"Error retrieving maintenance periods: {str(e)}"

    def get_automated_tasks(self) -> str:
        """
        Retrieve all automated tasks from Zabbix.
        """
        try:
            tasks = self.zabbix.task.get(output=["taskid", "name", "status", "type"])
            if not tasks:
                return "No automated tasks found in Zabbix."

            formatted_tasks = "\n".join(
                f"Task ID: {task['taskid']}\n  Name: {task['name']}\n  Status: {'Completed' if task['status'] == '1' else 'Pending'}\n  Type: {task['type']}"
                for task in tasks
            )
            return f"Automated Tasks in Zabbix:\n{formatted_tasks}"

        except Exception as e:
            self.logger.error(f"Error retrieving automated tasks: {e}")
            return f"Error retrieving automated tasks: {str(e)}"

    def get_zabbix_task_status(self, task_id: str) -> str:
        """
        Retrieve the status of a specific task in Zabbix.
        """
        try:
            task = self.zabbix.task.get(taskids=task_id, output=["taskid", "name", "status", "type"])
            if not task:
                return f"No task found with ID: {task_id}"

            task = task[0]  # Retrieve the first result
            status = "Completed" if task['status'] == '1' else "Pending"
            return (
                f"Task Details:\n"
                f"Task ID: {task['taskid']}\n"
                f"Name: {task['name']}\n"
                f"Status: {status}\n"
                f"Type: {task['type']}"
            )

        except Exception as e:
            self.logger.error(f"Error retrieving task status for task ID '{task_id}': {e}")
            return f"Error retrieving task status for task ID '{task_id}': {str(e)}"

    def get_notification_settings(self) -> str:
        """
        Retrieve notification settings from Zabbix.
        """
        try:
            media_types = self.zabbix.mediatype.get(output=["mediatypeid", "description", "type", "status"])
            if not media_types:
                return "No notification settings found in Zabbix."

            type_map = {
                "0": "Email",
                "1": "Script",
                "2": "SMS",
                "3": "Jabber",
                "4": "Ez Texting",
                "5": "Webhook"
            }
            status_map = {"0": "Enabled", "1": "Disabled"}
            formatted_media = "\n".join(
                f"Media Type ID: {media['mediatypeid']}\n"
                f"  Description: {media['description']}\n"
                f"  Type: {type_map.get(media['type'], 'Unknown')}\n"
                f"  Status: {status_map.get(media['status'], 'Unknown')}"
                for media in media_types
            )
            return f"Notification Settings in Zabbix:\n{formatted_media}"

        except Exception as e:
            self.logger.error(f"Error retrieving notification settings: {e}")
            return f"Error retrieving notification settings: {str(e)}"

    def get_zabbix_status(self) -> str:
        """
        Retrieve current Zabbix server status and resource usage.
        
        :return: Formatted Zabbix status information as a table
        """
        try:
            version = self.zabbix.apiinfo.version()
            users = self.zabbix.user.get(output=['userid'], limit=1)
            auth_status = "Successful" if users else "Failed"
            hosts = self.zabbix.host.get(output=['hostid'], limit=1)
            api_status = "Operational" if hosts else "Degraded"
            host_count = len(self.zabbix.host.get(filter={"status": "0"}))
            trigger_count = len(self.zabbix.trigger.get(filter={"status": "0"}))

            # Memory usage (example values, replace with actual API calls as needed)
            memory_info = self.zabbix.item.get(
                search={"key_": "system.mem"},
                output=["lastvalue"]
            )
            memory_used = memory_info[0]['lastvalue'] if memory_info else "N/A"
            
            # Construct status table
            status_response = f"""
            🔍 Zabbix System Status:
            +------------------------+-------------------+
            | Metric                 | Value             |
            +------------------------+-------------------+
            | Zabbix Version         | {version}         |
            | Authentication Status   | {auth_status}     |
            | API Status             | {api_status}      |
            | Monitored Hosts        | {host_count}      |
            | Active Triggers        | {trigger_count}   |
            | Memory Usage           | {memory_used}     |
            +------------------------+-------------------+
            """
            
            return status_response.strip()
        
        except Exception as e:
            self.logger.error(f"Error retrieving Zabbix status: {e}")
            return "Error retrieving Zabbix status."

def initialize_zabbix_tools(zabbix_client):
    """
    Initialize Zabbix tools with a given Zabbix client
    """
    zabbix_tools = ZabbixToolFunctions(zabbix_client)
    # Define individual tool functions
    def get_hosts(limit: int = None):
        return zabbix_tools.get_hosts(page_size=limit or 50)
    def get_items():
        return zabbix_tools.get_items()
    def get_hosts_limit(limit=50, page=1, page_size=50):
        return zabbix_tools.get_hosts_limit(limit, page, page_size)
    def get_triggers(limit: Optional[int] = None, severity: Optional[List[str]] = None):
        """
        Wrapper function for retrieving Zabbix triggers
        
        :param limit: Optional number of triggers to retrieve
        :param severity: Optional list of severity levels to filter
        :return: Formatted trigger information
        """
        return zabbix_tools.get_triggers(limit=limit, severity_filter=severity)

    def get_events():
        return zabbix_tools.get_events()
    def get_host_status():
        return zabbix_tools.get_host_status()
    def get_item_values():
        return zabbix_tools.get_item_values()
    def get_host_inventory():
        return zabbix_tools.get_host_inventory()
    def get_host_alerts():
        return zabbix_tools.get_host_alerts()
    def get_application_items():
        return zabbix_tools.get_application_items()
    def get_item_by_key(key):
        return zabbix_tools.get_item_by_key(key)
    def get_event_history():
        return zabbix_tools.get_event_history()
    def get_alert_history():
        return zabbix_tools.get_alert_history()
    def get_system_performance():
        return zabbix_tools.get_system_performance()
    def get_trigger_performance():
        return zabbix_tools.get_trigger_performance()
    def get_graph_data(graph_id):
        return zabbix_tools.get_graph_data(graph_id)
    def get_trend_data(item_id, time_from, time_to):
        return zabbix_tools.get_trend_data(item_id, time_from, time_to)
    def get_metrics_by_host(host_id):
        return zabbix_tools.get_metrics_by_host(host_id)
    def get_zabbix_performance_data():
        return zabbix_tools.get_zabbix_performance_data()
    def get_db_performance():
        return zabbix_tools.get_db_performance()
    def get_network_performance():
        return zabbix_tools.get_network_performance()
    def get_proxy_performance():
        return zabbix_tools.get_proxy_performance()
    def get_sla_data(sla_id):
        return zabbix_tools.get_sla_data(sla_id)
    def get_users():
        return zabbix_tools.get_users()
    def get_user_groups():
        return zabbix_tools.get_user_groups()
    def get_user_roles():
        return zabbix_tools.get_user_roles()
    def get_custom_item(key):
        return zabbix_tools.get_custom_item(key)
    def get_items_by_host_group(group_id):
        return zabbix_tools.get_items_by_host_group(group_id)
    def get_host_by_name(name):
        return zabbix_tools.get_host_by_name(name)
    def get_trigger_by_expression(expression):
        return zabbix_tools.get_trigger_by_expression(expression)
    def get_dependencies_by_trigger(trigger_id):
        return zabbix_tools.get_dependencies_by_trigger(trigger_id)
    def get_screens():
        return zabbix_tools.get_screens()
    def get_graphs_by_host(host_id):
        return zabbix_tools.get_graphs_by_host(host_id)
    def get_zabbix_api_limits():
        return zabbix_tools.get_zabbix_api_limits()
    def get_scheduled_tasks():
        return zabbix_tools.get_scheduled_tasks()
    def get_host_maintenance(host_id):
        return zabbix_tools.get_host_maintenance(host_id)
    def get_maintenance_periods():
        return zabbix_tools.get_maintenance_periods()
    def get_automated_tasks():
        return zabbix_tools.get_automated_tasks()
    def get_zabbix_task_status(task_id):
        return zabbix_tools.get_zabbix_task_status(task_id)
    def get_notification_settings():
        return zabbix_tools.get_notification_settings()
    def get_zabbix_status():
        """
        Retrieve the current Zabbix server status.
        """
        return zabbix_tools.get_zabbix_status()
    
    # Return all tools
    return [
        Tool(name="Get Hosts", func=get_hosts, description="Retrieve a list of hosts."),
        Tool(name="Get Hosts Limit", func=get_hosts_limit, description="Retrieve a limited number of hosts with pagination."),
        Tool(name="Get Items", func=get_items, description="Retrieve a list of items."),
        Tool(name="Get Triggers", func=get_triggers, description="Retrieve triggers with optional limit and severity filtering."),
        Tool(name="Get Events", func=get_events, description="Retrieve events."),
        Tool(name="Get Host Status", func=get_host_status, description="Get host statuses."),
        Tool(name="Get Item Values", func=get_item_values, description="Get item values."),
        Tool(name="Get Host Inventory", func=get_host_inventory, description="Get host inventory."),
        Tool(name="Get Host Alerts", func=get_host_alerts, description="Get host alerts."),
        Tool(name="Get Application Items", func=get_application_items, description="Get application items."),
        Tool(name="Get Item by Key", func=get_item_by_key, description="Retrieve item using key."),
        Tool(name="Get Event History", func=get_event_history, description="Get event history."),
        Tool(name="Get Alert History", func=get_alert_history, description="Get alert history."),
        Tool(name="Get System Performance", func=get_system_performance, description="Get system performance."),
        Tool(name="Get Trigger Performance", func=get_trigger_performance, description="Get trigger performance."),
        Tool(name="Get Graph Data", func=get_graph_data, description="Get graph data."),
        Tool(name="Get Trend Data", func=get_trend_data, description="Get trend data."),
        Tool(name="Get Metrics by Host", func=get_metrics_by_host, description="Get metrics by host."),
        Tool(name="Get Zabbix Performance Data", func=get_zabbix_performance_data, description="Get Zabbix performance data."),
        Tool(name="Get DB Performance", func=get_db_performance, description="Get database performance."),
        Tool(name="Get Network Performance", func=get_network_performance, description="Get network performance."),
        Tool(name="Get Proxy Performance", func=get_proxy_performance, description="Get proxy performance."),
        Tool(name="Get SLA Data", func=get_sla_data, description="Get SLA data."),
        Tool(name="Get Users", func=get_users, description="Retrieve a list of users from Zabbix."),
        Tool(name="Get User Groups", func=get_user_groups, description="Get user groups."),
        Tool(name="Get User Roles", func=get_user_roles, description="Get user roles."),
        Tool(name="Get Custom Item", func=get_custom_item, description="Get custom item by key."),
        Tool(name="Get Items by Host Group", func=get_items_by_host_group, description="Get items by host group."),
        Tool(name="Get Host by Name", func=get_host_by_name, description="Get host by name."),
        Tool(name="Get Trigger by Expression", func=get_trigger_by_expression, description="Get trigger by expression."),
        Tool(name="Get Dependencies by Trigger", func=get_dependencies_by_trigger, description="Get dependencies."),
        Tool(name="Get Screens", func=get_screens, description="Get all screens."),
        Tool(name="Get Graphs by Host", func=get_graphs_by_host, description="Get graphs for host."),
        Tool(name="Get Zabbix API Limits", func=get_zabbix_api_limits, description="Get API limits."),
        Tool(name="Get Scheduled Tasks", func=get_scheduled_tasks, description="Get scheduled tasks."),
        Tool(name="Get Host Maintenance", func=get_host_maintenance, description="Get host maintenance."),
        Tool(name="Get Maintenance Periods", func=get_maintenance_periods, description="Get maintenance periods."),
        Tool(name="Get Automated Tasks", func=get_automated_tasks, description="Get automated tasks."),
        Tool(name="Get Zabbix Task Status", func=get_zabbix_task_status, description="Get task status."),
        Tool(name="Get Notification Settings", func=get_notification_settings, description="Get notification settings."),
        Tool(name="Get System Performance", func=get_zabbix_status, description="Retrieve system performance metrics like CPU load, memory, and disk usage."
        ),
    ]
